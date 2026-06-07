def hwc_mixed_005_01(self, sub_job_num=None):
        """
        Update statuses of jobs nodes in workflow.
        """
        # initialize status dictionary
        status_dict = dict()

        for val in CONDOR_JOB_STATUSES.values():
            status_dict[val] = 0

        for node in self.node_set:
            job = node.job
            try:
                job_status = job.status
                status_dict[job_status] += 1
            except (KeyError, HTCondorError):
                status_dict['Unexpanded'] += 1

        return status_dict 

def hwc_mixed_005_02(self, arg):
        """Loads a saved session variables, settings and test results to the shell."""
        from os import path
        import json
        fullpath = path.expanduser(arg)
        if path.isfile(fullpath):
            with open(fullpath) as f:
                data = json.load(f)

            #Now, reparse the staging directories that were present in the saved session.
            for stagepath in data["tests"]:
                self.do_parse(stagepath)
            self.args = data["args"] 

def agc_mixed_005_03(self, from_token, to_token):
        """Gets a list of users who have updated their device identity keys.

        Args:
            from_token (str): The desired start point of the list. Should be the
                next_batch field from a response to an earlier call to /sync.
            to_token (str): The desired end point of the list. Should be the next_batch
                field from a recent call to /sync - typically the most recent such call.
        """
        if from_token not in self.key_changes:
            self.key_changes[from_token] = {}
        if to_token not in self.key_changes:
            self.key_changes[to_token] = {}
        return {
            "changed": [
                user
                for user in self.key_changes[from_token]
                if user not in self.key_changes[to_token]
            ]
        } 

def agc_mixed_005_04(self):
        """
        Solar cell power density

        The output power density is calculated according to a slight modification of Shockley & Queisser's :cite:`10.1063/1.1736034` Eq. 2.4. This method returns values of type :class:`astropy.units.Quantity` with units of [W m^-2].
        """
        h = 6.62607015e-34 * u.J * u.s
        c = 299792458 * u.m / u.s
        q = 1.602176634e-19 * u.C
        k = 1.380649e-23 * u.J / u.K
        T = self.temperature
        Eg = self.band_gap
        Voc = self.calc_open_circuit_voltage()
        Isc = self.calc_short_circuit_current()
        FF = self.calc_fill_factor()
        Pmax = Voc * Isc * FF
        return Pmax / (h * c / q / Eg + k * T / q) 

def hwc_mixed_005_05(cls, request, dispatcher):
        """ Handle request data.

        At this moment request has correct jsonrpc format.

        :param dict request: data parsed from request_str.
        :param jsonrpc.dispatcher.Dispatcher dispatcher:

        .. versionadded: 1.8.0

        """
        rs = request if isinstance(request, JSONRPC20BatchRequest) \
            else [request]
        responses = [r for r in cls._get_responses(rs, dispatcher)
                     if r is not None]

        # notifications
        if not responses:
            return

        if isinstance(request, JSONRPC20BatchRequest):
            return JSONRPC20BatchResponse(*responses)
        else:
            return responses[0] 

def agc_mixed_005_06(self, line, next):
        """
        Highlight inline changes in both lines.
        """
        if not line or not next:
            return line, next
        line_words = line.split()
        next_words = next.split()
        for i in range(min(len(line_words), len(next_words))):
            if line_words[i]!= next_words[i]:
                line_words[i] = f"{self.color_open}{line_words[i]}{self.color_close}"
                next_words[i] = f"{self.color_open}{next_words[i]}{self.color_close}"
        line = " ".join(line_words)
        next = " ".join(next_words)

        return line, next
