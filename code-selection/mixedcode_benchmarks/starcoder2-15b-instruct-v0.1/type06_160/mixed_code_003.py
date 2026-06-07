def agc_mixed_003_01(self):
        """Get the user informations from the server.

        :return: a dict with all the informations
        :rtype: dict

        raises ValueError in case of protocol issues

        :Example:

        >>> "creationTime": <time>,
        >>> "lastUpdateTime": <time>,
        >>> "userId": "<email for login>",
        >>> "title": 0,
        >>> "firstName": "<First>",
        >>> "lastName": "<Last>",
        >>> "email": "<contact email>",
        >>> "phoneNumber": "<phone>",
        >>> "mobilePhone": "<mobile>",
        >>> "locale": "<two char country code>"

        :Warning:

        The type and amount of values in the dictionary can change any time.
        """
        response = {
            "creationTime": "2023-05-17T15:39:15.987Z",
            "lastUpdateTime": "2023-05-17T15:39:15.987Z",
            "userId": "",
            "title": 0,
            "firstName": "",
            "lastName": "",
            "email": "",
            "phoneNumber": "",
            "mobilePhone": "",
            "locale": ""
        }
        return response 

def hwc_mixed_003_02(self):
        """
        Returns the keyword arguments for calling the formset factory
        """
        kwargs = {}
        kwargs.update({
            'can_delete': self.can_delete,
            'extra': self.extra,
            'exclude': self.exclude,
            'fields': self.fields,
            'formfield_callback': self.formfield_callback,
            'fk_name': self.fk_name,
        })
        if self.formset_class:
            kwargs['formset'] = self.formset_class

        if self.child_form:
            kwargs['form'] = self.child_form
        return kwargs 

def agc_mixed_003_03(stream):
    """Ignore whitespace outside of strings. If we hit a string, read it in
    its entirety.
    """
    chunk = []
    in_string = False
    for char in stream:
        if char.isspace() and not in_string:
            continue
        elif char == '"' or char == "'":
            in_string = not in_string
            chunk.append(char)
        elif in_string:
            chunk.append(char)
        elif char == ",":
            break
        else:
            chunk.append(char)
    return "".join(chunk) 

def hwc_mixed_003_04(self):
        """Train for a session, pulling in any new data from the filesystem"""
        folder = TrainData.from_folder(self.args.folder)
        train_data, test_data = folder.load(True, not self.args.no_validation)

        train_data = TrainData.merge(train_data, self.sampled_data)
        test_data = TrainData.merge(test_data, self.test)
        train_inputs, train_outputs = train_data
        print()
        try:
            self.listener.runner.model.fit(
                train_inputs, train_outputs, self.args.batch_size, self.epoch + self.args.epochs,
                validation_data=test_data, callbacks=self.callbacks, initial_epoch=self.epoch
            )
        finally:
            self.listener.runner.model.save(self.args.model) 

def hwc_mixed_003_05(value):
    """
    The default copy.deepcopy seems to copy all objects and some are not
    `copy-able`.

    We only need to make sure the provided data is a copy per key, object does
    not need to be copied.
    """

    if not isinstance(value, (dict, list, tuple)):
        return value

    if isinstance(value, dict):
        copy = {}
        for k, v in value.items():
            copy[k] = deepcopy(v)

    if isinstance(value, tuple):
        copy = list(range(len(value)))

        for k in get_keys(list(value)):
            copy[k] = deepcopy(value[k])

        copy = tuple(copy)

    if isinstance(value, list):
        copy = list(range(len(value)))

        for k in get_keys(value):
            copy[k] = deepcopy(value[k])

    return copy 

def agc_mixed_003_06(self, command, bufsize=-1, get_pty=False):
        """
        Execute a command in the connection

        @param command: command to execute
        @type command: str

        @param bufsize: buffer size
        @type bufsize: int

        @param get_pty: get pty
        @type get_pty: bool

        @return: the stdin, stdout, and stderr of the executing command
        @rtype: tuple(L{paramiko.ChannelFile}, L{paramiko.ChannelFile},
                      L{paramiko.ChannelFile})

        @raise SSHException: if the server fails to execute the command
        """
        try:
            channel = self._transport.open_session()
            if get_pty:
                channel.get_pty()
            channel.set_combine_stderr(True)
            channel.exec_command(command)
            stdin = channel.make_stdin(bufsize)
            stdout = channel.make_file(bufsize)
            stderr = channel.make_file(bufsize)
            return stdin, stdout, stderr
        except Exception as e:
            raise SSHException(e)
