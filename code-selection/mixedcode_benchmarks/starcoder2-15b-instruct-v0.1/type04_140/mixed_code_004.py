def agc_mixed_004_01(image,
                  lang=None,
                  config='',
                  nice=0,
                  output_type=Output.STRING):
    """
    Returns string containing box boundaries, confidences,
    and other information. Requires Tesseract 3.05+
    """

    if not isinstance(image, Image):
        raise TypeError('image must be an instance of PIL.Image.Image')
    if lang is not None and not isinstance(lang, str):
        raise TypeError('lang must be a string')
    if not isinstance(config, str):
        raise TypeError('config must be a string')
    if not isinstance(nice, int):
        raise TypeError('nice must be an integer')
    if not isinstance(output_type, Output):
        raise TypeError('output_type must be an instance of Output')
    command = ['tesseract', image.filename,'stdout', '-l', lang, config, '--oem', nice, '--output-base', output_type]
    process = subprocess.run(command, capture_output=True, text=True)
    return process.stdout 

def hwc_mixed_004_02(self, **kwargs):
        """Check whether the database is internally consistent

        We check that all variables are equal to the sum of their sectoral
        components and that all the regions add up to the World total. If
        the check is passed, None is returned, otherwise a dictionary of
        inconsistent variables is returned.

        Note: at the moment, this method's regional checking is limited to
        checking that all the regions sum to the World region. We cannot
        make this more automatic unless we start to store how the regions
        relate, see
        [this issue](https://github.com/IAMconsortium/pyam/issues/106).

        Parameters
        ----------
        kwargs: passed to `np.isclose()`
        """
        inconsistent_vars = {}
        for variable in self.variables():
            diff_agg = self.check_aggregate(variable, **kwargs)
            if diff_agg is not None:
                inconsistent_vars[variable + "-aggregate"] = diff_agg

            diff_regional = self.check_aggregate_region(variable, **kwargs)
            if diff_regional is not None:
                inconsistent_vars[variable + "-regional"] = diff_regional

        return inconsistent_vars if inconsistent_vars else None 

def agc_mixed_004_03(self):
        """Return the size of the period in days.

        >>> period('month', '2012-2-29', 4).size_in_days
        28
        >>> period('year', '2012', 1).size_in_days
        366
        """
        if self.unit =='month':
            start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
            end_date = start_date + timedelta(days=self.length * 30)
            return (end_date - start_date).days
        elif self.unit == 'year':
            start_date = datetime.strptime(self.start_date, '%Y')
            end_date = start_date + timedelta(days=self.length * 365)
            return (end_date - start_date).days
        else:
            raise ValueError("Invalid unit") 

def agc_mixed_004_04(results, times, N_matrix, ifprint):
    """
        Finds actions, angles and frequencies for box orbit.
        Takes a series of phase-space points from an orbit integration at times t and returns
        L = (act,ang,n_vec,toy_aa, pars) -- explained in find_actions() below.
    """
    act = []
    ang = []
    n_vec = []
    toy_aa = []
    pars = []

    for i in range(len(results)):
        result = results[i]
        time = times[i]
        N = N_matrix[i]
        act_i, ang_i, n_vec_i, toy_aa_i, pars_i = find_actions(result, time, N, ifprint)
        act.append(act_i)
        ang.append(ang_i)
        n_vec.append(n_vec_i)
        toy_aa.append(toy_aa_i)
        pars.append(pars_i)

    return act, ang, n_vec, toy_aa, pars 

def hwc_mixed_004_05(gelf_dict, record):
        """Add debugging fields to the given ``gelf_dict``

        :param gelf_dict: dictionary representation of a GELF log.
        :type gelf_dict: dict

        :param record: :class:`logging.LogRecord` to extract debugging
            fields from to insert into the given ``gelf_dict``.
        :type record: logging.LogRecord
        """
        gelf_dict.update({
            'file': record.pathname,
            'line': record.lineno,
            '_function': record.funcName,
            '_pid': record.process,
            '_thread_name': record.threadName,
        })
        # record.processName was added in Python 2.6.2
        pn = getattr(record, 'processName', None)
        if pn is not None:
            gelf_dict['_process_name'] = pn 

def hwc_mixed_004_06(msg):
    """Takes email.message.Message object initialized from unicode string,
    returns dict with header fields."""
    headers = {}
    for k in msg.keys():
        # decode_header decodes header but does not convert charset, so these
        # may still be bytes, even in Python 3. However, if it's ASCII
        # only (hence unambiguous encoding), the header fields come back
        # as str (unicode) in Python 3.
        (header_txt, charset) = email.header.decode_header(msg[k])[0]
        if charset is not None:
            header_txt = header_txt.decode(charset)
        headers[k] = header_txt
    return headers
