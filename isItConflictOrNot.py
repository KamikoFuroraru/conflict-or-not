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
        ui.setconfig('ui', 'merge', 'internal:fail')
        conflictOrNot = commands.merge(ui, repo, tool='internal:fail')

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