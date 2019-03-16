from mercurial import registrar, commands, hg

cmdtable = {}
command = registrar.command(cmdtable)


@command('isItConflictOrNot')
def isItConflictOrNot(ui, repo, dest=None):
    """Print there will be a conflict after merge or not."""
    path = repo.root
    localClonePath = path + '-local'
    remoteClonePath = path + '-remote'

    commands.clone(ui, path, localClonePath)

    if dest is None:
        dest = ui.config('paths', 'default')
        commands.clone(ui, dest, remoteClonePath)
    else:
        commands.clone(ui, dest, remoteClonePath)

    repo = hg.repository(ui, remoteClonePath)
    commands.pull(ui, repo, localClonePath)

    try:
        commands.update(ui, repo)

        ui.setconfig('ui', 'merge', 'internal:fail')
        conflictOrNot = commands.merge(ui, repo, tool='internal:fail')

    except Exception, e:
        import traceback
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