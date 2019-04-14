from mercurial import registrar, commands, hg
import traceback

cmdtable = {}
command = registrar.command(cmdtable)


@command('isItConflictOrNot')
def isItConflictOrNot(ui, repo, dest=None):
    """Print there will be a conflict after merge or not."""
    path = repo.root
    localClonePath = path + '-local'
    remoteClonePath = path + '-remote'

    if dest is None:
        dest = ui.config('paths', 'default')
        commands.clone(ui, dest, remoteClonePath)
    else:
        try:
            commands.clone(ui, dest, remoteClonePath)
        except Exception as e:
            traceback.print_exc(e)
            ui.write('\nNo repository found on this path.\n')
            return 0

    commands.clone(ui, path, localClonePath)
    repo = hg.repository(ui, remoteClonePath)
    commands.pull(ui, repo, localClonePath)

    try:
        commands.update(ui, repo)
        conflictOrNot = commands.merge(ui, repo)

        ui.pushbuffer()
        commands.resolve(ui, repo, list=True)
        uFilesStr = ui.popbuffer()
        import re
        uFilesStr = re.sub(r'U ', '', uFilesStr)
        uFilesList = re.split(r'\n', uFilesStr)
        uFilesList = list(filter(None, uFilesList))

        for uFile in uFilesList:
            commands.resolve(ui, repo, mark=uFile)

        commands.commit(ui, repo, message='Unresolved files')

        import os.path
        for uFile in uFilesList:
            ui.write('\n' + uFile + '\n')
            commands.cat(ui, repo, file1=os.path.join(remoteClonePath, uFile))

    except Exception as e:
        traceback.print_exc(e)
        conflictOrNot = False

    if conflictOrNot is True:
        ui.write('\nYes, here is a conflict\n')
    else:
        ui.write('\nNo, everything cool\n')

    repo = hg.repository(ui, path)

    import shutil

    shutil.rmtree(localClonePath)
    shutil.rmtree(remoteClonePath)

    return 0


def reposetup(ui, repo):
    ui.setconfig('ui', 'merge', 'internal:merge3')
