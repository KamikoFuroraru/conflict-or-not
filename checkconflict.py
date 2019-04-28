import os.path
import re
import traceback
import shutil
import json

from mercurial import commands, hg, registrar
from mercurial.error import NoMergeDestAbort, RepoError
from mercurial.i18n import _

cmdtable = {}
command = registrar.command(cmdtable)


@command('checkconflict',
         [('', 'clear_cache_list', None, _('clear all cache-list')),
          ('', 'set_cache_repo', None, _('set source to cache repo')),
          ('', 'check_file', '', _('shows the differences between base, local and remote copy')), ],
         '[OPTION]... [SOURCE]')
def checkconflict(ui, repo, source=None, **opts):
    """Print there will be a conflict after merge or not."""

    check_uncommited_changes(repo)

    cur_dir = repo.root
    local_clone_dir = cur_dir + '-local'
    remote_clone_dir = cur_dir + '-remote'

    default_source = repo.ui.config('paths', 'default')

    # if the source is not specified,
    # we take the default one from the repo configuration.
    # otherwise we take source

    if source is None:
        clone_source = default_source
    else:
        clone_source = source

    # path to the cache list
    cache_dir = os.path.expanduser('~\\.hg.cache')
    cache_list = os.path.join(cache_dir, 'cache_list.json')

    # if the source is local, then just clone

    if hg.islocal(clone_source):
        clone(repo, clone_source, remote_clone_dir)

    # otherwise, open the cache list and see
    # if it contains path information to the cache
    # of the specified resource for the current working repo

    else:
        cache_source = None

        # clear the cache list if this option is set, or
        # if the cache list does not exist, create it

        if not os.path.exists(cache_list) or opts.get('clear_cache_list'):
            if not os.path.exists(cache_dir):
                make_dir(cache_dir)
            create_cache_list(cache_list)
        else:
            data = read_cache_list(cache_list)
            cache_source = find_cache_src(data, cur_dir, clone_source, for_remove=False)

        # if the cache resource is found but this path does not exist or the path exists,
        # but it is not a repo, or set_cache_repo option,
        # we delete information about this cache repo from the cache list

        was_cached = cache_source is not None
        if was_cached and not is_repo(repo, str(cache_source)) or opts.get('set_cache_repo'):
            cache_list_data = read_cache_list(cache_list)
            cache_list_data = find_cache_src(cache_list_data, cur_dir, clone_source, for_remove=True)

            write_cache_list(cache_list, cache_list_data, add=False)

            repo.ui.write('\nThe last path to the cache repository is broken.\n')
            cache_source = None

        # if the cache resource is not found
        # suggest to choose the path to the cash repo
        # if the paths exists and empty -> clone,
        # if the path exists and repo -> checkupdate
        # else: select empty folder

        if cache_source is None:
            cache_source = str(raw_input('Specify the path for the cache-repository,\n'
                                         'or if no path it will be use /user/.hg.cache path.\n')).replace('\r', '')
            if not cache_source:
                cache_source = default_cache_src(cur_dir, cache_dir)
            if os.path.exists(cache_source):
                if not os.listdir(cache_source):
                    clone(repo, clone_source, cache_source)  # clone from the resource to the cache
                elif is_repo(repo, str(cache_source)):
                    repo = hg.repository(repo.ui, cache_source)
                    if clone_source == repo.ui.config('paths', 'default'):
                        check_update(repo, clone_source)
                        repo = hg.repository(repo.ui, cur_dir)
                    else:
                        repo = hg.repository(repo.ui, cur_dir)
                        repo.ui.write('\nCache-repo and remote-repo do not match.\n')
                        return 0
                else:
                    repo.ui.write('\nYou must select an empty folder or an existing repo folder.\n')
                    return 0
            else:
                make_dir(cache_source)
                clone(repo, clone_source, cache_source)

            note = gen_note(cur_dir, clone_source, cache_source)
            write_cache_list(cache_list, note, add=True)

        # if the cache resource is found,
        # check if new changes can be pulled.
        # if yes, pull and update

        else:
            repo = hg.repository(repo.ui, str(cache_source))
            check_update(repo, clone_source)
            repo = hg.repository(repo.ui, cur_dir)

        # finally clone from cache to remote
        clone(repo, str(cache_source), remote_clone_dir)

    # create a local repo clone
    clone(repo, cur_dir, local_clone_dir)

    repo = hg.repository(repo.ui, remote_clone_dir)  # go to remote repo clone
    commands.pull(repo.ui, repo, local_clone_dir)  # pull changes from a local repo clone to it
    commands.update(repo.ui, repo)  # update

    repo.ui.pushbuffer()
    conflict = do_merge(repo)
    deleted_str = repo.ui.popbuffer()
    deleted_list = re.findall('\'(.*)\'', deleted_str)

    # if there is a conflict,
    # we look at the list of files with conflicts
    # and display them, because merge3 will mark conflicting lines with special tags

    if conflict:
        repo.ui.pushbuffer()
        commands.resolve(repo.ui, repo, list=True)
        u_files_str = repo.ui.popbuffer()
        u_files_list = re.findall('U (.*)\n', u_files_str)

        if opts.get('check_file'):
            file = opts.get('check_file')
            if file in deleted_list:
                repo.ui.write(
                    '\nfile ' + file + ' was deleted in other [merge rev] but was modified in local [working '
                                       'copy].\n')
            elif file in u_files_list:
                show_file_merge(repo, remote_clone_dir, file)
            else:
                repo.ui.write('\nFile ' + str(file) + ' does not cause conflict.\n'
                                                      'The conflict occurs in the following files:\n')
                show_all_conflicts(repo, u_files_list, deleted_list)

        else:
            show_all_conflicts(repo, u_files_list, deleted_list)

        repo.ui.write('\nYes, here is a conflict\n')

    # if there is no conflict, say it
    else:
        repo.ui.write('\nNo, everything cool\n')

    # go back to our work repo
    repo = hg.repository(repo.ui, cur_dir)

    # delete clones
    remove_clones(local_clone_dir, remote_clone_dir)

    return 0


def reposetup(ui, repo):
    repo.ui.setconfig('ui', 'merge', 'internal:merge3')
    repo.ui.setconfig('ui', 'interactive', 'no')


def check_uncommited_changes(repo):
    repo.ui.pushbuffer()
    commands.status(repo.ui, repo)
    uncommited_changes = repo.ui.popbuffer()

    if uncommited_changes:
        do_check = str(raw_input('\nYou have uncommitted changes.\n'
                                 'Checking will be done by the last commited changes.\n'
                                 'If you are not satisfied with this situation,\n'
                                 'commit the latest changes and restart the command (press n to abort) ')).replace('\r',
                                                                                                                   '')
        if do_check == 'n':
            return 0


def clone(repo, from_source, to_source):
    try:
        commands.clone(repo.ui, from_source, to_source)
    except RepoError as e:
        traceback.print_exc(e)
        return 0


def remove_clones(local_clone_dir, remote_clone_dir):
    shutil.rmtree(local_clone_dir)
    shutil.rmtree(remote_clone_dir)


def check_update(repo, clone_source):
    if commands.incoming(repo.ui, repo, bundle=None, force=False) == 0:
        commands.pull(repo.ui, repo, clone_source)
        commands.update(repo.ui, repo)


def is_repo(repo, source):
    try:
        # return a repository object for the specified path or rep not found
        hg.repository(repo.ui, source)
        return True
    except RepoError as e:
        traceback.print_exc(e)
        return False


def make_dir(dir):
    try:
        os.makedirs(dir)
    except OSError as e:
        traceback.print_exc(e)
        return 0


def create_cache_list(cache_list):
    write_cache_list(cache_list, [], add=False)


def read_cache_list(cache_list):
    with open(cache_list) as f:
        return json.load(f)


def write_cache_list(cache_list, cache_note, add):
    if add:
        data = read_cache_list(cache_list)
        data.append(cache_note)
    else:
        data = cache_note
    try:
        with open(cache_list, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        traceback.print_exc(e)
        return 0


def find_cache_src(data, cur_dir, clone_source, for_remove):
    for note in data:
        work_dir = note['work_dir'] == cur_dir
        source_dir = note['source_dir'] == clone_source
        if work_dir and source_dir:
            if for_remove:
                data.remove(note)
                return data
            else:
                return note['cache_dir']


def gen_note(wrk_dir, src_dir, ch_dir):
    work_dir = wrk_dir
    source_dir = src_dir
    cache_dir = ch_dir

    note = {
        'work_dir': work_dir,
        'source_dir': source_dir,
        'cache_dir': cache_dir
    }

    return note


def default_cache_src(cur_dir, cache_dir):
    path = os.path.normpath(cur_dir).split(os.path.sep)
    return os.path.join(cache_dir, path[-1] + '_cache')


def do_merge(repo):
    try:
        return commands.merge(repo.ui, repo)
    except NoMergeDestAbort as e:
        traceback.print_exc(e)
        return False


def show_all_conflicts(repo, u_list, d_list):
    repo.ui.write('\n')
    for uFile in u_list:
        if uFile in d_list:
            repo.ui.write(
                'file ' + uFile + ' was deleted in other [merge rev] but was modified in local [working '
                                  'copy].\n')
        else:
            repo.ui.write(uFile + '\n')
    repo.ui.write('\n')


def show_file_merge(repo, remote_clone_dir, file):
    try:
        with open(os.path.join(remote_clone_dir, file), 'r') as f:
            repo.ui.write('\n' + f.read() + '\n')
    except IOError as e:
        traceback.print_exc(e)
        return 0
