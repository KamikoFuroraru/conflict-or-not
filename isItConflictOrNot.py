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
        with open(cache_list, 'a') as f: pass

    if hg.islocal(clone_source):
        commands.clone(repo.ui, clone_source, remote_clone_dir)
    else:
        cache_source = None
        cache_source_repo = None
        with open(cache_list, 'r') as f:
            lines = f.readlines()
            f.seek(0)
            for line in lines:
                if line.startswith(cur_dir + clone_source):
                    cache_source = line[:-1].replace(cur_dir + clone_source, '')
                    cache_source_repo = os.path.join(cache_source,
                                                     '.hg')

        if (cache_source_repo is not None) and (not os.path.exists(cache_source_repo)):
            with open(cache_list, 'r+') as f:
                lines = f.readlines()
                f.seek(0)
                for line in lines:
                    if line != (str(cur_dir + clone_source + cache_source) + '\n'):
                        f.write(line)
                f.truncate()
            cache_source = None

        if cache_source is None:
            cache_source = str(raw_input('Specify the path for the cache-repository.\n')).replace('\r', '')
            with open(cache_list, 'a') as f:
                f.write(cur_dir + clone_source + cache_source + '\n')
            os.makedirs(cache_source)
            commands.clone(repo.ui, clone_source, cache_source)
        else:
            repo = hg.repository(repo.ui, cache_source)
            if commands.incoming(repo.ui, repo, bundle=None, force=False) == 0:
                commands.pull(repo.ui, repo, clone_source)
                commands.update(repo.ui, repo)
            repo = hg.repository(repo.ui, cur_dir)

        commands.clone(repo.ui, cache_source, remote_clone_dir)

    commands.clone(repo.ui, cur_dir, local_clone_dir)

    repo = hg.repository(repo.ui, remote_clone_dir)
    commands.pull(repo.ui, repo, local_clone_dir)
    commands.update(repo.ui, repo)
    conflict_or_not = commands.merge(repo.ui, repo)

    if conflict_or_not is True:
        repo.ui.pushbuffer()
        commands.resolve(repo.ui, repo, list=True)
        u_files_str = repo.ui.popbuffer()
        u_files_str = u_files_str.replace('U ', '')
        u_files_list = re.split(r'\n', u_files_str)
        u_files_list = list(filter(None, u_files_list))

        for uFile in u_files_list:
            repo.ui.write('\n' + uFile + '\n')
            with open(os.path.join(remote_clone_dir, uFile), 'r') as f:
                repo.ui.write(f.read())

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
