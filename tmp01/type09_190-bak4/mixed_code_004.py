def hwc_mixed_004_01(name, apps, exclude_packages=None, exclude_command_class=None):
    """
    Searches through the given apps to find the named command class. Skips
    over any packages specified by exclude_packages and any command class
    specified by exclude_command_class. Returns the last command class found
    or None if the command class could not be found.

    Django's command searching behavior is backwards with respect to other
    features like template and static file loaders. This function follows
    that convention.

    """
    if exclude_packages is None:
        exclude_packages = []
    for app in reversed(
        [app for app in apps if not issubpackage(app, exclude_packages)]):
        try:
            command_class = import_module(
                "{app:s}.management.commands.{name:s}".format(
                    app=app, name=name)).Command
        except (ImportError, AttributeError):
            pass
        else:
            if exclude_command_class is None or \
                not issubclass(command_class, exclude_command_class):
                return command_class
    return None 

def agc_mixed_004_02(self, bbox):
    """See base class for details."""
    # Validate the coordinates
    if not isinstance(bbox, np.ndarray):
        raise TypeError("bbox must be a numpy array")
    if bbox.shape!= (4,):
        raise ValueError("bbox must be a 1D array of length 4")
    if not np.issubdtype(bbox.dtype, np.floating):
        raise ValueError("bbox must be a floating-point array")
    if not np.all(np.isfinite(bbox)):
        raise ValueError("bbox must contain only finite values")
    if not np.all(bbox >= 0):
        raise ValueError("bbox must contain only non-negative values")
    if not np.all(bbox <= 1):
        raise ValueError("bbox must contain values in the range [0, 1]")
    encoded_example = np.zeros(self.encoded_example_size, dtype=np.float32)
    encoded_example[0] = bbox[0] * self.encoded_example_size
    encoded_example[1] = bbox[1] * self.encoded_example_size
    encoded_example[2] = np.log(bbox[2] / bbox[0]) * self.encoded_example_size
    encoded_example[3] = np.log(bbox[3] / bbox[1]) * self.encoded_example_size

    return encoded_example 

def agc_mixed_004_03(shape, inds=None, return_directions=True):
    """
    Get list of grid edges
    :param shape:
    :param inds:
    :param return_directions:
    :return:
    """
    if inds is None:
        inds = np.arange(np.prod(shape)).reshape(shape)
    edges = []
    directions = []
    for i in range(shape[0]):
        for j in range(shape[1]):
            if i < shape[0] - 1:
                edges.append([inds[i, j], inds[i + 1, j]])
                directions.append([0, 1])
            if j < shape[1] - 1:
                edges.append([inds[i, j], inds[i, j + 1]])
                directions.append([1, 0])
    if return_directions:
        return edges, directions
    else:
        return edges 

def agc_mixed_004_04(self, **kwargs):
        """
        Return pandas DataFrame with the most important results stored in the timers.
        """
        data = []
        for name, timer in self.items():
            data.append({
                'name': name,
                'total': timer.total_time,
                'calls': timer.ncalls,
                'average': timer.avg_time,
               'std': timer.std_time,
               'min': timer.min_time,
               'max': timer.max_time,
            })
        df = pd.DataFrame(data)
        return df 

def hwc_mixed_004_05(self, editor, refresh=True):
        """
        Set associated editor/web page:
            codeeditor.base.TextEditBaseWidget
            browser.WebView
        """
        self.editor = editor
        # Note: This is necessary to test widgets/editor.py
        # in Qt builds that don't have web widgets
        try:
            from qtpy.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            QWebEngineView = type(None)
        self.words_button.setVisible(not isinstance(editor, QWebEngineView))
        self.re_button.setVisible(not isinstance(editor, QWebEngineView))
        from spyder.plugins.editor.widgets.codeeditor import CodeEditor
        self.is_code_editor = isinstance(editor, CodeEditor)
        self.highlight_button.setVisible(self.is_code_editor)
        if refresh:
            self.refresh()
        if self.isHidden() and editor is not None:
            self.clear_matches() 

def hwc_mixed_004_06(amount_w: int,
                       entropy_w: Union[int, float],
                       entropy_n: Union[int, float],
                       amount_n: int) -> float:
    """Calculate the entropy of a passphrase with given words and numbers."""
    if not isinstance(amount_w, int):
        raise TypeError('amount_w can only be int')
    if not isinstance(entropy_w, (int, float)):
        raise TypeError('entropy_w can only be int or float')
    if not isinstance(entropy_n, (int, float)):
        raise TypeError('entropy_n can only be int or float')
    if not isinstance(amount_n, int):
        raise TypeError('amount_n can only be int')
    if amount_w < 0:
        raise ValueError('amount_w should be greater than 0')
    if entropy_w < 0:
        raise ValueError('entropy_w should be greater than 0')
    if entropy_n < 0:
        raise ValueError('entropy_n should be greater than 0')
    if amount_n < 0:
        raise ValueError('amount_n should be greater than 0')

    return float(amount_w * entropy_w + amount_n * entropy_n)
