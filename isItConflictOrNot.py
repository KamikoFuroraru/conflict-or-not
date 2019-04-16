from mercurial import registrar, commands, hg
import traceback
import os, errno
import re

cmdtable = {}
command = registrar.command(cmdtable)

CACHE = os.path.expanduser('~/.hg.cache')


@command('isItConflictOrNot')
def isItConflictOrNot(ui, repo, source=None):
    """Print there will be a conflict after merge or not."""
    cur_dir = repo.root
    local_clone_dir = cur_dir + '-local'
    remote_clone_dir = cur_dir + '-remote'

    default_source = repo.ui.config('paths', 'default')

    if source is None:
        clone_source = default_source
    else:
        clone_source = source

    cache_list = os.path.join(CACHE, 'cache_list')

    if not os.path.exists(cache_list):
        f = open(cache_list, 'a')
        f.close()

    try:
        if hg.islocal(clone_source):
            commands.clone(repo.ui, clone_source, remote_clone_dir)

        else:
            f = open(cache_list, 'a+')
            cache_source = None
            cache_source_repo = None
            for line in f:
                if line.startswith(cur_dir + clone_source):
                    cache_source = line[:-1].replace(cur_dir + clone_source, '')
                    cache_source_repo = os.path.join(cache_source, '.hg') # == False -> need to remove from list WANT OPTION TO CLEAN THISSSSS ALLLLLLLLLLLLLLL
                    break
            if (cache_source is None) or (not os.path.exists(cache_source_repo)):
                cache_source = str(raw_input('Specify the path for the cache-repository.\n')).replace('\r', '')
                try:
                    os.makedirs(cache_source)
                    f.write(cur_dir + clone_source + cache_source + '\n')
                    f.close()
                    commands.clone(repo.ui, clone_source, cache_source)
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise
            else:
                repo = hg.repository(repo.ui, cache_source)
                if commands.incoming(repo.ui, repo, bundle=None, force=False) == 0:
                    commands.pull(repo.ui, repo, clone_source)
                    commands.update(repo.ui, repo)
                repo = hg.repository(repo.ui, cur_dir)

            commands.clone(repo.ui, cache_source, remote_clone_dir)

    except Exception as e:
        traceback.print_exc(e)
        return 0

    commands.clone(repo.ui, cur_dir, local_clone_dir)
    repo = hg.repository(repo.ui, remote_clone_dir)
    commands.pull(repo.ui, repo, local_clone_dir)

    try:
        commands.update(repo.ui, repo)
        conflict_or_not = commands.merge(repo.ui, repo)

        repo.ui.pushbuffer()
        commands.resolve(repo.ui, repo, list=True)
        u_files_str = repo.ui.popbuffer()
        u_files_str = u_files_str.replace('U ', '')
        u_files_list = re.split(r'\n', u_files_str)
        u_files_list = list(filter(None, u_files_list))

        for uFile in u_files_list:
            f = open(os.path.join(remote_clone_dir, uFile), 'r')
            repo.ui.write('\n' + uFile + '\n')
            repo.ui.write(f.read())
            f.close()

    except Exception as e:
        traceback.print_exc(e)
        conflict_or_not = False

    if conflict_or_not is True:
        repo.ui.write('\nYes, here is a conflict\n')
    else:
        repo.ui.write('\nNo, everything cool\n')

    repo = hg.repository(repo.ui, cur_dir)

    import shutil

    shutil.rmtree(local_clone_dir)
    shutil.rmtree(remote_clone_dir)

    return 0


def reposetup(ui, repo):
    repo.ui.setconfig('ui', 'merge', 'internal:merge3')
