def hwc_mixed_002_01(self, age):
        """Get the fill color depending on age.

        Args:
            age (int): The age of the branch/es

        Returns:
            tuple: (r, g, b)
        """
        if age == self.tree.age:
            return self.leaf_color
        color = self.stem_color
        tree = self.tree

        if len(color) == 3:
            return color

        diff = [color[i+3]-color[i] for i in range(3)]
        per_age = [diff[i]/(tree.age-1) for i in range(3)]

        return tuple([int(color[i]+per_age[i]*age) for i in range(3)]) 

def agc_mixed_002_02(self, opTable, group_by_cols, meas):
        """ 
        Create an aggregate table grouped by col showing meas
        The meas is something like "sum(in)" or "count(*)"
        RETURNS:
            DROP TABLE C_AGG_PRODUCT;
            CREATE TABLE C_AGG_PRODUCT AS (
                SELECT PRODUCT, sum(AMOUNT) AS result 
                FROM C_SALES GROUP BY PRODUCT
            );

        """
        temp_table = "C_AGG_PRODUCT"
        # Create the table
        sql = "DROP TABLE IF EXISTS %s;" % temp_table
        self.cursor.execute(sql)
        sql = "CREATE TABLE %s AS (SELECT %s, %s FROM %s GROUP BY %s);" % (temp_table, group_by_cols, meas, opTable, group_by_cols)
        self.cursor.execute(sql)
        # Return the table name
        return temp_table 

def agc_mixed_002_03(response, server_url):
    """Adapt a POST response to a Message.

    @type response: L{openid.fetchers.HTTPResponse}
    @param response: Result of a POST to an OpenID endpoint.

    @rtype: L{openid.message.Message}

    @raises openid.fetchers.HTTPFetchingError: if the server returned a
        status of other than 200 or 400.

    @raises ServerError: if the server returned an OpenID error.
    """
    # Should this function be named Message.fromHTTPResponse instead?
    if response.status == 200:
        return _httpResponseToMessage200(response, server_url)
    elif response.status == 400:
        return _httpResponseToMessage400(response, server_url)
    else:
        raise HTTPFetchingError(
            'HTTP status %d' % response.status,
            response.status,
            response.headers,
            response.body) 

def hwc_mixed_002_04(self, filename):
        # type: (str) -> None
        """
        Open up an existing ISO for inspection and modification.

        Parameters:
         filename - The filename containing the ISO to open up.
        Returns:
         Nothing.
        """
        if self._initialized:
            raise pycdlibexception.PyCdlibInvalidInput('This object already has an ISO; either close it or create a new object')

        fp = open(filename, 'r+b')
        self._managing_fp = True
        try:
            self._open_fp(fp)
        except Exception:
            fp.close()
            raise 

def agc_mixed_002_05(wavfile, station, channel, debug=0):
    """
    Inner loop for parallel checks.

    :type wavfile: str
    :param wavfile: Wavefile path name to look in.
    :type station: str
    :param station: Channel name to check for
    :type channel: str
    :param channel: Channel name to check for
    :type debug: int
    :param debug: Debug level, if > 1, will output what it it working on.
    """
    if debug > 1:
        print("Checking %s" % wavfile)
    try:
        with WavFile(wavfile) as wav:
            if station in wav.stations:
                if channel in wav.stations[station]:
                    return True
    except Exception:
        pass
    return False 

def hwc_mixed_002_06(self, col_number, col_label):
        """
        Add drop-down-menu options for magic_method_codes columns
        """
        if self.data_type == 'age':
            method_list = vocab.age_methods
        elif '++' in col_label:
            method_list = vocab.pmag_methods
        elif self.data_type == 'result':
            method_list = vocab.pmag_methods
        else:
            method_list = vocab.er_methods
        self.choices[col_number] = (method_list, True)
