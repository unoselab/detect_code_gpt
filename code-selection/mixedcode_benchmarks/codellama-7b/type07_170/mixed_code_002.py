def hwc_mixed_002_01(
            self,
            assoc_id,
            evidence_line_bnode
    ):
        """
        Add assertion level provenance, currently always IMPC
        :param assoc_id:
        :param evidence_line_bnode:
        :return:
        """
        provenance_model = Provenance(self.graph)
        model = Model(self.graph)
        assertion_bnode = self.make_id(
            "assertion{0}{1}".format(assoc_id, self.localtt['IMPC']), '_')

        model.addIndividualToGraph(assertion_bnode, None, self.globaltt['assertion'])

        provenance_model.add_assertion(
            assertion_bnode, self.localtt['IMPC'],
            'International Mouse Phenotyping Consortium')

        self.graph.addTriple(
            assoc_id, self.globaltt['proposition_asserted_in'], assertion_bnode)

        self.graph.addTriple(
            assertion_bnode,
            self.resolve('is_assertion_supported_by_evidence'),  # "SEPIO:0000111"
            evidence_line_bnode)

        return 

def agc_mixed_002_02(self, metric, ts, point, sd_point):
        """Convert an OC metric point to a SD point."""
        if metric.type == MetricType.GAUGE:
            return self._convert_gauge(metric, ts, point, sd_point)
        elif metric.type == MetricType.COUNTER:
            return self._convert_counter(metric, ts, point, sd_point)
        elif metric.type == MetricType.TIMER:
            return self._convert_timer(metric, ts, point, sd_point)
        elif metric.type == MetricType.HISTOGRAM:
            return self._convert_histogram(metric, ts, point, sd_point)
        elif metric.type == MetricType.METER:
            return self._convert_meter(metric, ts, point, sd_point)
        else:
            raise ValueError("Unsupported metric type: %s" % metric.type) 

def hwc_mixed_002_03(self, extra_params=None):
        """
        All Tags in this Ticket
        """

        # Default params
        params = {
            'per_page': settings.MAX_PER_PAGE,
        }

        if extra_params:
            params.update(extra_params)

        return self.api._get_json(
            Tag,
            space=self,
            rel_path=self.space._build_rel_path(
                'tickets/%s/tags' % self['number']
            ),
            extra_params=params,
            get_all=True,  # Retrieve all tags in the ticket
        ) 

def hwc_mixed_002_04(self, attr_name, prefix=None):
        """Write attribute's value to a file.

        :param str attr_name:
            Attribute's name to be logged

        :param str prefix:
            Optional. Attribute's name that is prefixed to logging message,
            defaults to ``None``.

        :returns: message written to file
        :rtype: str
        """
        if self._folder is None:
            return

        separator = "\t"
        attr = getattr(self.obj, attr_name)
        if hasattr(attr, '__iter__'):
            msg = separator.join([str(e) for e in attr])
        else:
            msg = str(attr)

        if prefix is not None:
            msg = "{}\t{}".format(getattr(self.obj, prefix), msg)

        path = self.get_file(attr_name)
        with open(path, 'a') as f:
            f.write("{}\n".format(msg))

        return msg 

def agc_mixed_002_05(self, casename=None, var_name='mountpoint', suffix='', in_paths=False):
        """Creates a directory that can be used as a mountpoint. The directory is stored in :attr:`mountpoint`,
        or the varname as specified by the argument. If in_paths is True, the path is stored in the :attr:`_paths`
        attribute instead.

        :returns: the mountpoint path
        :raises NoMountpointAvailableError: if no mountpoint could be made
        """
        if casename is None:
            casename = self.casename
        if var_name == 'mountpoint':
            var_name = self.mountpoint_var_name
        if in_paths:
            var_name = self._paths_var_name
        if var_name not in self.config:
            self.config[var_name] = {}
        if casename not in self.config[var_name]:
            self.config[var_name][casename] = {}
        if suffix not in self.config[var_name][casename]:
            self.config[var_name][casename][suffix] = tempfile.mkdtemp(prefix='casemount-')
        return self.config[var_name][casename][suffix] 

def agc_mixed_002_06(cls, *args, **kwargs):
        """
        This method is used within urls.py to create unique formwizard
        instances for every request. We need to override this method because
        we add some kwargs which are needed to make the formwizard usable.
        """
        cls.form_list = kwargs.pop('form_list', cls.form_list)
        cls.form_entry_name = kwargs.pop('form_entry_name', cls.form_entry_name)
        cls.form_exit_name = kwargs.pop('form_exit_name', cls.form_exit_name)
        cls.form_template = kwargs.pop('form_template', cls.form_template)
        cls.done_step_name = kwargs.pop('done_step_name', cls.done_step_name)
        cls.done_step_template = kwargs.pop('done_step_template', cls.done_step_template)
        cls.form_list_template = kwargs.pop('form_list_template', cls.form_list_template)
        cls.form_entry_template = kwargs.pop('form_entry_template', cls.form_entry_template)
        cls.form_exit_template = kwargs.pop('form_exit_template', cls.form_exit_template)
        cls.form_entry_view = kwargs.pop('form_entry_view', cls.form_entry_view)
        cls.form_exit_view = kwargs.pop('form_exit_view', cls.form_exit_view)
        cls.form_entry_url = kwargs.pop('form_entry_url', cls.form_entry_url)
        cls.form_exit_url = kwargs.pop('form_exit_url', cls.form_exit_url)
        cls.form_entry_view_kwargs = kwargs.pop('form_entry_view_kwargs', cls.form_entry_view_kwargs)
        cls.form_exit_view_kwargs = kwargs.pop('form_exit_view_kwargs', cls.form_exit_view_kwargs)
