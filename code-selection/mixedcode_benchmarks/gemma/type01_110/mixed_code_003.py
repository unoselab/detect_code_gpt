def agc_mixed_003_01(self, sites, rup, dists, imt, stddev_types):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.get_mean_and_stddevs>`
        for spec of input and result values.
        """

        # get mean and std using the superclass
        mean = self.get_mean(sites, rup, dists, imt)
        if stddev_types == "constant":
            stddev = self.stddev
        elif stddev_types == "variable":
            stddev = self.get_stddev(sites, rup, dists, imt)
        else:
            raise ValueError(f"Unknown stddev_types: {stddev_types}")
        return mean, stddev 

def hwc_mixed_003_02(self, data):
		"""Construct info about a project from artefact

		:param data:	golang-project-packages artefact
		:type  data:	json/dict
		"""
		occurrences = {}
		main_occurrences = {}

		# occurrences of devel packages
		for pkg in data["data"]["dependencies"]:
			package = pkg["package"]
			for item in pkg["dependencies"]:
				dep = item["name"]
				if package != ".":
					deps = map(lambda l: "%s/%s" % (package, l), item["location"])
				else:
					deps = item["location"]
				if dep not in occurrences:
					occurrences[dep] = deps
				else:
					occurrences[dep] = occurrences[dep] + deps

		self.occurrences = occurrences

		# occurrences of main packages
		for main in data["data"]["main"]:
			filename = main["filename"]
			for dep in main["dependencies"]:
				if dep not in main_occurrences:
					main_occurrences[dep] = [filename]
				else:
					main_occurrences[dep].append(filename)

		self.main_occurrences = main_occurrences

		# test directories
		self.test_directories = sorted(map(lambda l: l["test"], data["data"]["tests"]))

		# provided devel packages
		self.provided_packages = sorted(data["data"]["packages"])

		# imported paths in devel packages
		imported_packages = []
		imported_native_packages = []
		for path in occurrences:
			try:
				self.ipparser.parse(path)
			except ValueError:
				continue

			if self.ipparser.isNative():
				imported_native_packages.append(path)
			else:
				imported_packages.append(path)

		self.imported_packages = sorted(imported_packages)
		self.imported_native_packages = sorted(imported_native_packages)

		# main packages
		self.main_packages = map(lambda l: l["filename"], data["data"]["main"]) 

def agc_mixed_003_03(self, evals, iteration=0, feval=None):
        # pylint: disable=invalid-name
        """Evaluate  a set of data.

        Parameters
        ----------
        evals : list of tuples (DMatrix, string)
            List of items to be evaluated.
        iteration : int
            Current iteration.
        feval : function
            Custom evaluation function.

        Returns
        -------
        result: str
            Evaluation result string.
        """
        results = []
        for dmat, name in evals:
            if feval:
                score = feval(self.model, dmat)
            else:
                score = self.model.predict(dmat)
            results.append(f"{name}: {score}")
        return ", ".join(results) 

def agc_mixed_003_04(self, email_messages):
        """Sends one or more EmailMessage objects and returns the number of
        email messages sent.
        """
        sent_count = 0
        for message in email_messages:
            try:
                self.send_message(message)
                sent_count += 1
            except Exception:
                continue
        return sent_count 

def hwc_mixed_003_05(args):
    """Compare method configuration definitions across workspaces. Ignores
       methodConfigVersion if the verbose argument is not set"""
    config_1 = config_get(args).splitlines()
    args.project = args.Project
    args.workspace = args.Workspace
    cfg_1_name = args.config
    if args.Config is not None:
        args.config = args.Config
    if args.Namespace is not None:
        args.namespace = args.Namespace
    config_2 = config_get(args).splitlines()
    if not args.verbose:
        config_1 = skip_cfg_ver(config_1)
        config_2 = skip_cfg_ver(config_2)
    return list(unified_diff(config_1, config_2, cfg_1_name, args.config, lineterm='')) 

def hwc_mixed_003_06(self):
        """Calculate beginning and end of log events."""
        # get start datetime
        first = self.coll_handle.find_one(None, sort=[("ts", ASCENDING)])
        last = self.coll_handle.find_one(None, sort=[("ts", DESCENDING)])

        self._start = first['ts']
        if self._start.tzinfo is None:
            self._start = self._start.replace(tzinfo=tzutc())

        self._end = last['ts']
        if self._end.tzinfo is None:
            self._end = self._end.replace(tzinfo=tzutc())

        return True
