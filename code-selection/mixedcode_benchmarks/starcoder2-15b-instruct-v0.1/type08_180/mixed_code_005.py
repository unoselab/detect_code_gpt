def hwc_mixed_005_01(self, data, return_bool=False):
        """ ???

        Parameters
        ----------
        data            : pd.DataFrame()
            Input dataframe.
        return_bool     : bool
            ???

        Returns
        -------
        pd.DataFrame()
            ???

        """

        # This returns the full table with True where the condition is true
        if return_bool == False:
            data = self._find_missing_return_frame(data)
            return data

        # This returns a bool selector if any of the column is True
        elif return_bool == "any":
            bool_sel = self._find_missing_return_frame(data).any(axis=0)
            return bool_sel

        # This returns a bool selector if all of the column are True
        elif return_bool == "all":
            bool_sel = self._find_missing_return_frame(data).all(axis=0)
            return bool_sel

        else:
            print("error in multi_col_how input") 

def agc_mixed_005_02(self) -> Optional[Batch]:
        """
        Return a single batch or ``None`` signaling epoch end.

        .. note::
            Signal the epoch end with ``None``.

        Stop when:
        - stream ends and epoch size is not set
        - specified number of batches is returned

        :return: a single batch or ``None`` signaling epoch end
        """
        if self._stream is None:
            return None
        try:
            batch = next(self._stream)
        except StopIteration:
            if self._epoch_size is None:
                return None
            else:
                self._stream = iter(self._dataset)
                batch = next(self._stream)
        self._batches_seen += 1
        if self._batches_seen >= self._epoch_size:
            self._stream = None
        return batch 

def agc_mixed_005_03(raw_crash, processed_crash):
    """
    Takes a raw crash and a processed crash (these are Socorro-centric
    data structures) and converts them to a crash data structure used
    by signature generation.

    :arg raw_crash: raw crash data from Socorro
    :arg processed_crash: processed crash data from Socorro

    :returns: crash data structure that conforms to the schema

    """
    # We want to generate fresh signatures, so we remove the "normalized" field
    # from stack frames from the processed crash because this is essentially
    # cached data from previous processing
    crash_data = {}
    crash_data['date'] = raw_crash['date']
    crash_data['product'] = raw_crash['product']
    crash_data['version'] = raw_crash['version']
    crash_data['build'] = raw_crash['build']
    crash_data['platform'] = raw_crash['platform']
    crash_data['os_version'] = raw_crash['os_version']
    crash_data['architecture'] = raw_crash['architecture']
    crash_data['address'] = processed_crash['address']
    crash_data['stack_trace'] = processed_crash['stack_trace']
    crash_data['install_age'] = processed_crash['install_age']
    crash_data['user_comments'] = processed_crash['user_comments']
    crash_data['cpu_info'] = processed_crash['cpu_info']
    crash_data['ram_info'] = processed_crash['ram_info']
    crash_data['main_crash'] = processed_crash['main_crash']
    crash_data['install_time'] = processed_crash['install_time']
    crash_data['last_crash_time'] = processed_crash['last_crash_time']
    crash_data['last_update_time'] = processed_crash['last_update_time']
    crash_data['process_type'] = processed_crash['process_type']
    crash_data['process_name'] = processed_crash['process_name']
    crash_data['user_id'] = processed_crash['user_id']
    crash_data['user_name'] = processed_crash['user_name']
    crash_data['user_email'] = processed_crash['user_email']
    crash_data['install_year'] = processed_crash['install_year']
    crash_data['install_month'] = processed_crash['install_month']
    crash_data['install_day'] = processed_crash['install_day']
    crash_data['install_hour'] = processed_crash['install_hour']
    crash_data['install_minute'] = processed_crash['install_minute']
    crash_data['install_second'] 

def agc_mixed_005_04(num, default):
        """check if the format of number is (num)(G|m|B) i.e 500GB, 200mb. 400
        etc.. """
        pattern = r"^(\d+)(G|M|B)$"
        match = re.match(pattern, num)
        if match:
            size, unit = match.groups()
            size = int(size)
            if unit == "G":
                return size * 1000 ** 3
            elif unit == "M":
                return size * 1000 ** 2
            elif unit == "B":
                return size
        return default 

def hwc_mixed_005_05(text):
    """Article title formatter.

    Except functional words, first letter uppercase. Example:
    "Google Killing Annoying Browsing Feature"

    **中文文档**

    文章标题的格式, 除了虚词, 每个英文单词的第一个字母大写。
    """
    text = text.strip()
    if len(text) == 0:  # if empty string, return it
        return text
    else:
        text = text.lower()  # lower all char
        # delete redundant empty space
        chunks = [chunk for chunk in text.split(" ") if len(chunk) >= 1]

        new_chunks = list()
        for chunk in chunks:
            if chunk not in _function_words:
                chunk = chunk[0].upper() + chunk[1:]
            new_chunks.append(chunk)

        new_chunks[0] = new_chunks[0][0].upper() + new_chunks[0][1:]

        return " ".join(new_chunks) 

def hwc_mixed_005_06(traceback):
    """
    For internal use only (until further notice)
    """
    if email().format == 'html':
        try:
            from pygments import highlight
            from pygments.lexers import PythonTracebackLexer
            from pygments.formatters import HtmlFormatter
            with_pygments = True
        except ImportError:
            with_pygments = False

        if with_pygments:
            formatter = HtmlFormatter(noclasses=True)
            wrapped = highlight(traceback, PythonTracebackLexer(), formatter)
        else:
            wrapped = '<pre>%s</pre>' % traceback
    else:
        wrapped = traceback

    return wrapped
