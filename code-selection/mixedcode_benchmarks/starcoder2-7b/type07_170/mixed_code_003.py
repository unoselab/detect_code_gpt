def hwc_mixed_003_01(op):
    """ Given a list of registers like ['a', 'bc', 'h', 'hl'] returns
    a set of single registers: ['a', 'b', 'c', 'h', 'l'].
    Non register parameters, like numbers will be ignored.
    """
    result = set()
    if isinstance(op, str):
        op = [op]

    for x in op:
        if is_8bit_register(x):
            result = result.union([x])
        elif x == 'sp':
            result.add(x)
        elif x == 'af':
            result = result.union(['a', 'f'])
        elif x == "af'":
            result = result.union(["a'", "f'"])
        elif is_16bit_register(x):  # Must be a 16bit reg or we have an internal error!
            result = result.union([LO16(x), HI16(x)])

    return list(result) 

def agc_mixed_003_02(self, values, level=None):
        """
        Set new names on index. Each name has to be a hashable type.

        Parameters
        ----------
        values : str or sequence
            name(s) to set
        level : int, level name, or sequence of int/level names (default None)
            If the index is a MultiIndex (hierarchical), level(s) to set (None
            for all levels).  Otherwise level must be None

        Raises
        ------
        TypeError if each name is not hashable.
        """
        if not isinstance(values, (list, tuple)):
            values = [values]
        if level is None:
            level = range(len(self.levels))
        elif isinstance(level, (list, tuple)):
            level = [self.levels.get_loc(l) for l in level]
        else:
            level = [self.levels.get_loc(level)]
        for l in level:
            if not isinstance(values[l], Hashable):
                raise TypeError("Index values must be hashable")
            self.levels[l] = values[l] 

def agc_mixed_003_03(self, index1, index2):
        """
        Finds the difference between the indexes index1 and index2.

        Compares index1 with index2 and returns True if there are any
        differences or False in case there are no differences.

        :type index1: Index
        :type index2: Index

        :rtype: bool
        """
        if index1.get_name()!= index2.get_name():
            raise ValueError("Indexes have different names")

        if index1.get_type()!= index2.get_type():
            raise ValueError("Indexes have different types")

        if index1.get_columns()!= index2.get_columns():
            raise ValueError("Indexes have different columns")

        if index1.get_unique()!= index2.get_unique():
            raise ValueError("Indexes have different unique values")

        if index1.get_primary()!= index2.get_primary():
            raise ValueError("Indexes have different primary keys")

        if index1.get_foreign()!= index2.get_foreign():
            raise ValueError("Indexes have different foreign keys")

        return False 

def agc_mixed_003_04(self):
        """
        Construct a tensorflow function to compute the bound on the marginal
        likelihood.
        """
        log_likelihoods = []
        for i in range(self.num_data_points):
            log_likelihoods.append(self._build_likelihood_for_data_point(i))
        log_likelihood = tf.add_n(log_likelihoods)

        # We compute the bound on the marginal likelihood by adding the
        # log likelihood to the log prior.
        log_prior = self._build_log_prior()
        log_likelihood_bound = log_likelihood + log_prior

        # We compute the bound on the marginal likelihood by adding the
        # log likelihood to the log prior.
        log_likelihood_bound = log_likelihood + log_prior

        # We return the bound on the marginal likelihood.
        return log_likelihood_bound 

def hwc_mixed_003_05(self):
        """Removes the rating the calling user added for the specified item
        (POST only)."""
        url = "%s/deleteRating" % self.root
        params = {
            "f": "json",
        }
        return self._post(url,
                             params,
                             securityHandler=self._securityHandler,
                             proxy_port=self._proxy_port,
                             proxy_url=self._proxy_url) 

def hwc_mixed_003_06(self):
    """
    Export a DataFrame from the front-end visualization. For instance, a user
    can filter to show only a single cluster using the dendrogram and then
    get a dataframe of this cluster using the widget_df method.
    """

    if hasattr(self, 'widget_instance') == True:

      if self.widget_instance.mat_string != '':

        tmp_net = deepcopy(Network())

        df_string = self.widget_instance.mat_string

        tmp_net.load_file_as_string(df_string)

        df = tmp_net.export_df()

        return df

      else:
        return self.export_df()

    else:
      if hasattr(self, 'widget_class') == True:
        print('Please make the widget before exporting the widget DataFrame.')
        print('Do this using the widget method: net.widget()')

      else:
        print('Can not make widget because Network has no attribute widget_class')
        print('Please instantiate Network with clustergrammer_widget using: Network(clustergrammer_widget)')
