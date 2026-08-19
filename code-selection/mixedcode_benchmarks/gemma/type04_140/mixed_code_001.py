def agc_mixed_001_01(self, state_key):
        """
        Concreat method.

        Args:
            state_key       The key of state. this value is point in map.

        Returns:
            [(x, y)]

        """
        actions = []
        x, y = state_key
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if not self.map[nx][ny].is_obstacle:
                    actions.append((nx, ny))
        return actions 

def hwc_mixed_001_02(self, task, releasetype, descriptor):
        """Create and return a new model that represents taskfiles for the given task, releasetpye and descriptor

        :param task: the task of the taskfiles
        :type task: :class:`djadapter.models.Task`
        :param releasetype: the releasetype
        :type releasetype: str
        :param descriptor: the descirptor
        :type descriptor: str|None
        :returns: the created tree model
        :rtype: :class:`jukeboxcore.gui.treemodel.TreeModel`
        :raises: None
        """
        rootdata = treemodel.ListItemData(['Version', 'Releasetype', 'Path'])
        rootitem = treemodel.TreeItem(rootdata)
        for tf in task.taskfile_set.filter(releasetype=releasetype, descriptor=descriptor).order_by('-version'):
            tfdata = djitemdata.TaskFileItemData(tf)
            tfitem = treemodel.TreeItem(tfdata, rootitem)
            for note in tf.notes.all():
                notedata = djitemdata.NoteItemData(note)
                treemodel.TreeItem(notedata, tfitem)
        versionmodel = treemodel.TreeModel(rootitem)
        return versionmodel 

def agc_mixed_001_03(parser, token):
    """
    Performs a defined function on the passed arguments.
    Normally this returns the output of the function into the template.
    If the second to last argument is ``as``, the result of the function is stored in the context and is named whatever the last argument is.

    Syntax::

        {% [function] [var args...] [name=value kwargs...] [as varname] %}

    Examples::

        {% search '^(\d{3})$' 800 as match %}

        {% map sha1 hello world %}

    """
    args = parser.parse_args()
    kwargs = parser.parse_kwargs()

    var_name = None
    if len(args) >= 1 and args[-2] == 'as':
        var_name = args[-1]
        args = args[:-2]

    func_name = args[0]
    func_args = args[1:]

    # Assuming 'context' is available in the scope or attached to parser
    # and that functions are registered in a lookup table.
    func = parser.context.get_function(func_name)
    result = func(*func_args, **kwargs)

    if var_name:
        parser.context.set_variable(var_name, result)
        return ""

    return result 

def agc_mixed_001_04(rets, rfr_ann=0, mar=0, full=0, expanding=0):
    """Compute the sortino ratio as (Ann Rets - Risk Free Rate) / Downside Deviation Ann

    :param rets: period return series
    :param rfr_ann: annualized risk free rate
    :param mar: minimum acceptable rate of return (MAR)
    :param full: If True, use the lenght of full series. If False, use only values below MAR
    :param expanding:
    :return:
    """
    import numpy as np
    import pandas as pd

    rets = pd.Series(rets)
    n_periods = 252 if isinstance(rets.index, pd.DatetimeIndex) else len(rets)

    ann_ret = rets.mean() * n_periods
    rfr_period = rfr_ann / n_periods

    downside_diff = rets - (mar / n_periods)
    downside_rets = downside_diff.clip(upper=0)

    if full:
        downside_std = np.sqrt((downside_rets**2).mean())
    else:
        downside_std = np.sqrt((downside_rets**2).sum() / len(downside_rets[downside_rets < 0])) if len(downside_rets[downside_rets < 0]) > 0 else np.nan

    downside_dev_ann = downside_std * np.sqrt(n_periods)

    if downside_dev_ann == 0 or np.isnan(downside_dev_ann):
        return np.nan

    return (ann_ret - rfr_ann) / downside_dev_ann 

def hwc_mixed_001_05(self, cat, sub_cat, key=''):
        """Return the model name given cat/subcat or product key"""
        if cat + ':' + sub_cat in self.device_models:
            return self.device_models[cat + ':' + sub_cat]
        else:
            for i_key, i_val in self.device_models.items():
                if 'key' in i_val:
                    if i_val['key'] == key:
                        return i_val
            return False 

def hwc_mixed_001_06(path, mode=0o777, dir_fd=None):
    """
    Create a directory named path with numeric mode mode.

    Equivalent to "os.mkdir".

    Args:
        path (path-like object): Path or URL.
        mode (int): The mode parameter is passed to os.mkdir();
            see the os.mkdir() description for how it is interpreted.
            Not supported on cloud storage objects.
        dir_fd: directory descriptors;
            see the os.remove() description for how it is interpreted.
            Not supported on cloud storage objects.

    Raises:
        FileExistsError : Directory already exists.
        FileNotFoundError: Parent directory not exists.
    """
    system = get_instance(path)
    relative = system.relpath(path)

    # Checks if parent directory exists
    parent_dir = dirname(relative.rstrip('/'))
    if parent_dir:
        parent = path.rsplit(relative, 1)[0] + parent_dir + '/'
        if not system.isdir(parent):
            raise ObjectNotFoundError(
                "No such file or directory: '%s'" % parent)

    # Checks if directory not already exists
    if system.isdir(system.ensure_dir_path(path)):
        raise ObjectExistsError("File exists: '%s'" % path)

    # Create directory
    system.make_dir(relative, relative=True)
