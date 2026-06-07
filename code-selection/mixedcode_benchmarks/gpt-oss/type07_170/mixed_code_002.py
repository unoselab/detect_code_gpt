def hwc_mixed_002_01(self, dataset_path, dataset_path_type, name=None):
        """ Return remote path of this file (if staging is required) else None.
        """
        path = str(dataset_path)  # Use false_path if needed.
        action = self.action_mapper.action(path, dataset_path_type)
        if action.staging_needed:
            if name is None:
                name = os.path.basename(path)
            remote_directory = self.__remote_directory(dataset_path_type)
            remote_path_rewrite = self.path_helper.remote_join(remote_directory, name)
        else:
            # Actions which don't require staging MUST define a path_rewrite
            # method.
            remote_path_rewrite = action.path_rewrite(self.path_helper)

        return remote_path_rewrite 

def agc_mixed_002_02(self):
        """
        Handles the iteration by pulling the next line out of the stream,
        attempting to convert the response to JSON if necessary.

        :returns: Data representing what was seen in the feed
        """
        try:
            line = next(self._stream)
        except StopIteration:
            raise
        if isinstance(line, bytes):
            line = line.decode('utf-8')
        line = line.rstrip('\n')
        if getattr(self, "_json", False):
            import json
            try:
                return json.loads(line)
            except Exception:
                return line
        return line 

def agc_mixed_002_03(self, enforce_json, method, raise_for_status,
                      url, **kwargs):
        """Send HTTP request.

        Args:
             enforce_json (bool): Require properly-formatted JSON or raise :exc:`~pancloud.exceptions.PanCloudError`. Defaults to ``False``.
             method (str): HTTP method.
             raise_for_status (bool): If ``True``, raises :exc:`~pancloud.exceptions.HTTPError` if status_code not in 2XX. Defaults to ``False``.
             url (str): Request URL.
             **kwargs (dict): Re-packed key-word arguments.

         Returns:
            requests.Response: Requests Response() object

        """
        response = requests.request(method, url, **kwargs)

        if raise_for_status:
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise HTTPError(str(exc)) from exc

        if enforce_json:
            try:
                response.json()
            except ValueError as exc:
                raise PanCloudError("Response does not contain valid JSON") from exc

        return response 

def hwc_mixed_002_04(self):
        """Recreate repositories package lists
        """
        if len(self.args) == 1 and self.args[0] == "upgrade":
            Initialization(False).upgrade(only="")
        elif (len(self.args) == 2 and self.args[0] == "upgrade" and
                self.args[1].startswith("--only=")):
            repos = self.args[1].split("=")[-1].split(",")
            for rp in repos:
                if rp not in self.meta.repositories:
                    repos.remove(rp)
            Initialization(False).upgrade(repos)
        else:
            usage("") 

def agc_mixed_002_05(self):
        """Assemble a list of future alerts"""

        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        future = []
        for task in getattr(self, "tasks", []):
            task_time = task.get("time") or task.get("alert_time")
            if isinstance(task_time, datetime.datetime):
                if task_time.tzinfo is None:
                    task_time = task_time.replace(tzinfo=datetime.timezone.utc)
                if task_time > now:
                    future.append(task)
        return future 

def hwc_mixed_002_06(p):
    """ function_body : program_co END FUNCTION
                      | program_co END SUB
                      | statements_co END FUNCTION
                      | statements_co END SUB
                      | co_statements_co END FUNCTION
                      | co_statements_co END SUB
                      | END FUNCTION
                      | END SUB
    """
    if not FUNCTION_LEVEL:
        syntax_error(p.lineno(3), "Unexpected token 'END %s'. No Function or Sub has been defined." % p[2])
        p[0] = None
        return

    a = FUNCTION_LEVEL[-1].kind
    if a not in (KIND.sub, KIND.function):  # This function/sub was not correctly declared, so exit now
        p[0] = None
        return

    i = 2 if p[1] == 'END' else 3
    b = p[i].lower()

    if a != b:
        syntax_error(p.lineno(i), "Unexpected token 'END %s'. Should be 'END %s'" % (b.upper(), a.upper()))
        p[0] = None
    else:
        p[0] = None if p[1] == 'END' else p[1]
