# coding=utf-8
import os.path
import re
import traceback
import shutil

from mercurial import commands, hg, registrar
from mercurial.error import NoMergeDestAbort, RepoError
from mercurial.i18n import _

cmdtable = {}
command = registrar.command(cmdtable)


@command('isItConflictOrNot',
         [('', 'clear_cache_list', None, _('clear all cache-list')),
          ('', 'set_cache_repo', None, _('set source to cache repo')), ],
         '[OPTION]... [SOURCE]')
def isItConflictOrNot(ui, repo, source=None, **opts):
    """Print there will be a conflict after merge or not."""
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
    cache_list_source = os.path.expanduser('~/.hg.cache')
    cache_list = os.path.join(cache_list_source, 'cache_list')

    # clear the cache list if this option is set, or
    # if the cache list does not exist, create it
    if not os.path.exists(cache_list) or opts.get('clear_cache_list'):
        if not os.path.exists(cache_list_source):
            try:
                os.makedirs(cache_list_source)
            except OSError as e:
                traceback.print_exc(e)
                return 0
        try:
            with open(cache_list, 'w') as f:
                pass
        except IOError as e:
            traceback.print_exc(e)
            return 0

    # if the source is local, then just clone
    if hg.islocal(clone_source):
        try:
            commands.clone(repo.ui, clone_source, remote_clone_dir)
        except RepoError as e:
            traceback.print_exc(e)
            return 0

    # otherwise, open the cache list and see
    # if it contains path information to the cache
    # of the specified resource for the current working repo
    else:
        cache_source = None
        cache_source_repo = None
        try:
            with open(cache_list, 'r') as f:
                lines = f.readlines()
                f.seek(0)
                for line in lines:
                    # if there is such info, we say that this is the way to our cash repo
                    if line.startswith(cur_dir + clone_source):
                        cache_source = line[:-1].replace(cur_dir + clone_source, '')
                        cache_source_repo = os.path.join(cache_source, '.hg')
        except IOError as e:
            traceback.print_exc(e)
            return 0

        # if the cache resource is found but this path does not exist or the path exists,
        # but it is not a repo, or set_cache_repo option,
        # we delete information about this cache repo from the cache list
        was_cached = cache_source is not None
        set_cache = opts.get('set_cache_repo')
        if (was_cached and (not os.path.exists(cache_source) or not os.path.exists(cache_source_repo))) or set_cache:
            try:
                with open(cache_list, 'r+') as f:
                    lines = f.readlines()
                    f.seek(0)
                    for line in lines:
                        if line != (str(cur_dir + clone_source + cache_source) + '\n'):
                            f.write(line)
                    f.truncate()
            except IOError as e:
                traceback.print_exc(e)
                return 0
            repo.ui.write('\nThe last path to the cache repository is broken.\n')
            cache_source = None

        # if the cache resource is not found
        # suggest to choose the path to the cash repo
        # if the paths exists and empty -> clone,
        # if the path exists and repo -> checkupdate
        # else: select empty folder
        if cache_source is None:
            cache_source = str(raw_input('Specify the path for the cache-repository.\n')).replace('\r', '')
            if os.path.exists(cache_source):
                if not os.listdir(cache_source):
                    try:
                        commands.clone(repo.ui, clone_source, cache_source)  # clone from the resource to the cache
                    except RepoError as e:
                        traceback.print_exc(e)
                        return 0
                elif os.path.exists(os.path.join(cache_source, '.hg')):
                    checkupdate(repo, cache_source, clone_source, cur_dir)
                else:
                    repo.ui.write('\nYou must select an empty folder.\n')
                    return 0
            else:
                try:
                    os.makedirs(cache_source)
                except OSError as e:
                    traceback.print_exc(e)
                    return 0
                try:
                    commands.clone(repo.ui, clone_source, cache_source)
                except RepoError as e:
                    traceback.print_exc(e)
                    return 0
            try:
                with open(cache_list, 'a') as f:  # enter information about the new cache
                    f.write(cur_dir + clone_source + cache_source + '\n')
            except IOError as e:
                traceback.print_exc(e)
                return 0

        # if the cache resource is found,
        # check if new changes can be pulled.
        # if yes, pull and update
        else:
            checkupdate(repo, cache_source, clone_source, cur_dir)

        # finally create a cache clone as a remote repo clone
        try:
            commands.clone(repo.ui, cache_source, remote_clone_dir)
        except RepoError as e:
            traceback.print_exc(e)
            return 0

    # create a local repo clone
    try:
        commands.clone(repo.ui, cur_dir, local_clone_dir)
    except RepoError as e:
        traceback.print_exc(e)
        return 0

    # M = изменен (modified)
    # A = добавлен (added)
    # R = удален (removed)
    # C = без изменений (clean)
    # ! = отсутствует (missing) (удален внешней командой, отслеживается)
    # ? = не отслеживается
    # I = игнорируется (ignored)
    #   = источник предыдущего файла показанного как A (добавлен)

    # ?????
    
    repo.ui.pushbuffer()
    commands.status(repo.ui, repo)  # check status
    file_state_str = repo.ui.popbuffer()
    file_state_list = re.findall(' (.*)\n', file_state_str)
    removed_list = re.findall('R (.*)\n', file_state_str)
    add_list = re.findall('A (.*)\n', file_state_str)

    repo = hg.repository(repo.ui, local_clone_dir)

    # copying from working dir to local clone
    for mFile in file_state_list:
        cur_dir_mFile = os.path.join(cur_dir, mFile)
        local_clone_dir_mFile = os.path.join(local_clone_dir, mFile)
        try:
            if mFile in removed_list:
                commands.remove(repo.ui, repo, local_clone_dir_mFile)
            elif mFile in add_list:
                commands.add(repo.ui, repo, local_clone_dir_mFile)
            else:
                shutil.copy2(cur_dir_mFile, local_clone_dir_mFile)
        except IOError as e:
            traceback.print_exc(e)
            return 0

    # do commit inside local-clone
    commands.commit(repo.ui, repo, message='Modified files')

    repo = hg.repository(repo.ui, remote_clone_dir)  # go to remote repo clone
    commands.pull(repo.ui, repo, local_clone_dir)  # pull changes from a local repo clone to it
    commands.update(repo.ui, repo)  # update
    try:
        repo.ui.pushbuffer()
        conflict_or_not = commands.merge(repo.ui, repo)  # do merge3
        deleted_str = repo.ui.popbuffer()
        deleted_list = re.findall('\'(.*)\'', deleted_str)
    except NoMergeDestAbort as e:
        traceback.print_exc(e)
        conflict_or_not = False

    # if there is a conflict,
    # we look at the list of files with conflicts
    # and display them, because merge3 will mark conflicting lines with special tags
    if conflict_or_not is True:
        repo.ui.pushbuffer()
        commands.resolve(repo.ui, repo, list=True)
        u_files_str = repo.ui.popbuffer()
        u_files_list = re.findall('U (.*)\n', u_files_str)

        for uFile in u_files_list:
            repo.ui.write('\n' + uFile + '\n')
            try:
                if uFile in deleted_list:
                    repo.ui.write(
                        'file ' + uFile + 'was deleted in other [merge rev] but was modified in local [working '
                                          'copy].\n')
                else:
                    with open(os.path.join(remote_clone_dir, uFile), 'r') as f:
                        repo.ui.write(f.read() + '\n')
            except IOError as e:
                traceback.print_exc(e)
                return 0

        repo.ui.write('\nYes, here is a conflict\n')

    # if there is no conflict, say it
    else:
        repo.ui.write('\nNo, everything cool\n')

    # go back to our work repo
    repo = hg.repository(repo.ui, cur_dir)

    # delete clones
    shutil.rmtree(local_clone_dir)
    shutil.rmtree(remote_clone_dir)

    return 0


def reposetup(ui, repo):
    repo.ui.setconfig('ui', 'merge', 'internal:merge3')
    repo.ui.setconfig('ui', 'interactive', 'no')


def checkupdate(repo, cache_source, clone_source, cur_dir):
    repo = hg.repository(repo.ui, cache_source)
    if commands.incoming(repo.ui, repo, bundle=None, force=False) == 0:
        commands.pull(repo.ui, repo, clone_source)
        commands.update(repo.ui, repo)
    repo = hg.repository(repo.ui, cur_dir)
