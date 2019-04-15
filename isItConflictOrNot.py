from mercurial import registrar, commands, hg
import traceback
import os.path

cmdtable = {}
command = registrar.command(cmdtable)

CACHE = os.path.expanduser('~/.hg.cache')

@command('isItConflictOrNot')
def isItConflictOrNot(ui, repo, source=None):
    """Print there will be a conflict after merge or not."""
    curDir = repo.root
    localCloneDir = curDir + '-local'
    remoteCloneDir = curDir + '-remote'

    defaultSource = repo.ui.config('paths', 'default')

    if source == None:
        cloneSource = defaultSource
    else:
        cloneSource = source

    try:
        if hg.islocal(cloneSource) == False:
            import urllib
            cacheSource = os.path.join(CACHE, urllib.quote_plus(cloneSource))
            if os.path.exists(cacheSource):
                repo = hg.repository(repo.ui, cacheSource)
                if commands.incoming(repo.ui, repo, bundle=None, force=False) == 0:
                    commands.pull(repo.ui, repo, cloneSource)
                    commands.update(repo.ui, repo)
                repo = hg.repository(repo.ui, curDir)
            else:
                commands.clone(repo.ui, cloneSource, cacheSource)
            commands.clone(repo.ui, cacheSource, remoteCloneDir)
        else:
            commands.clone(repo.ui, cloneSource, remoteCloneDir)
    except Exception as e:
        traceback.print_exc(e)
        return 0

    commands.clone(repo.ui, curDir, localCloneDir)
    repo = hg.repository(repo.ui, remoteCloneDir)
    commands.pull(repo.ui, repo, localCloneDir)

    try:
        commands.update(repo.ui, repo)
        conflictOrNot = commands.merge(repo.ui, repo)

        repo.ui.pushbuffer()
        commands.resolve(repo.ui, repo, list=True)
        uFilesStr = repo.ui.popbuffer()
        import re
        uFilesStr = re.sub(r'U ', '', uFilesStr)
        uFilesList = re.split(r'\n', uFilesStr)
        uFilesList = list(filter(None, uFilesList))

        for uFile in uFilesList:
            commands.resolve(repo.ui, repo, mark=uFile)

        commands.commit(repo.ui, repo, message='Unresolved files')

        for uFile in uFilesList:
            repo.ui.write('\n' + uFile + '\n')
            commands.cat(repo.ui, repo, file1=os.path.join(remoteCloneDir, uFile))

    except Exception as e:
        traceback.print_exc(e)
        conflictOrNot = False

    if conflictOrNot is True:
        repo.ui.write('\nYes, here is a conflict\n')
    else:
        repo.ui.write('\nNo, everything cool\n')

    repo = hg.repository(repo.ui, curDir)

    import shutil

    shutil.rmtree(localCloneDir)
    shutil.rmtree(remoteCloneDir)

    return 0


def reposetup(ui, repo):
    repo.ui.setconfig('ui', 'merge', 'internal:merge3')
