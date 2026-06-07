def agc_mixed_001_01(self, data_dict):
        """Internal method that makes sure any dictionary elements
        are properly cast into the correct types, instead of
        just treating everything like a string from the csv file.

        Args:
            data_dict: dictionary containing bro log data.

        Returns:
            Cleaned Data dict.
        """
        for key, value in data_dict.items():
            if isinstance(value, str):
                try:
                    data_dict[key] = int(value)
                except ValueError:
                    try:
                        data_dict[key] = float(value)
                    except ValueError:
                        pass
        return data_dict 

def agc_mixed_001_02(self, xml):
        """
        Parse Outcome Request data from XML.
        """
        self.outcome_request = {}
        self.outcome_request['lti_message_type'] = xml.get('lti_message_type')
        self.outcome_request['lti_version'] = xml.get('lti_version')
        self.outcome_request['lti_result_sourcedid'] = xml.get('lti_result_sourcedid')
        self.outcome_request['lti_result_score_given'] = xml.get('lti_result_score_given')
        self.outcome_request['lti_result_score_maximum'] = xml.get('lti_result_score_maximum')
        self.outcome_request['lti_result_score_min'] = xml.get('lti_result_score_min')
        self.outcome_request['lti_result_score_raw'] = xml.get('lti_result_score_raw')
        self.outcome_request['lti_result_score_scaled'] = xml.get('lti_result_score_scaled')
        self.outcome_request['lti_result_sourcedids'] = xml.get('lti_result_sourcedids')
        self.outcome_request['lti_result_status'] = xml.get('lti_result_status')
        self.outcome_request['lti_result_url'] = xml.get('lti_result_url')
        self.outcome_request['lti_service'] = xml.get('lti_service')
        self.outcome_request['lti_service_url'] = xml.get('lti_service_url')
        self.outcome_request['lti_user_id'] = xml.get('lti_user_id')
        self.outcome_request['lti_user_image'] = xml.get('lti_user_image')
        self.outcome_request['lti_user_image_url'] = xml.get('lti_user_image_url')
        self.outcome_request['lti_user_name'] = xml.get 

def hwc_mixed_001_03(self, cmd_name):
        """
        Retrieves the possible name spaces and commands associated to the given
        command name.

        :param cmd_name: The given command name
        :return: A list of 2-tuples (name space, command)
        :raise ValueError: Unknown command name
        """
        namespace, command = _split_ns_command(cmd_name)
        if not namespace:
            # Name space not given, look for the commands
            spaces = self.__find_command_ns(command)
            if not spaces:
                # Unknown command
                raise ValueError("Unknown command {0}".format(command))
            else:
                # Return a sorted list of tuples
                return sorted((namespace, command) for namespace in spaces)

        # Single match
        return [(namespace, command)] 

def hwc_mixed_001_04(cls, v):
        """Coerce a value to the right type for the collection, or return it if
        it is already of the right type."""
        if isinstance(v, cls.itemtype):
            return v
        else:
            try:
                return cls.coerceitem(v)
            except Exception as e:
                raise exc.CollectionItemCoerceError(
                    itemtype=cls.itemtype,
                    colltype=cls,
                    passed=v,
                    exc=e,
                ) 

def hwc_mixed_001_05(self):
        """
        Starts or resumes the retrieval of messages from the server queue.

        This method starts receiving messages from the server, they will be
        passed to the consumer callback.

        .. note:: This is called automatically when :meth:`.consume` is called,
            so users should not need to call this unless :meth:`.pauseProducing`
            has been called.

        Returns:
            defer.Deferred: fired when the production is ready to start
        """
        # Start consuming
        self._running = True
        for consumer in self._consumers.values():
            queue_object, _ = yield consumer.channel.basic_consume(
                queue=consumer.queue, consumer_tag=consumer.tag
            )
            deferred = self._read(queue_object, consumer)
            deferred.addErrback(
                lambda f: _legacy_twisted_log.msg,
                "_read failed on consumer {c}",
                c=consumer,
                logLevel=logging.ERROR,
            )
        _legacy_twisted_log.msg("AMQP connection successfully established") 

def agc_mixed_001_06(self, on_quit=None):
        """
        Reads the standard input until the shell session is stopped

        :param on_quit: A call back method, called without argument when the
                        shell session has ended
        """
        # Start the init script
        while True:
            try:
                line = self.readline()
            except EOFError:
                break
            if line == '':
                break
            if line.startswith('!'):
                self.execute(line[1:])
            else:
                self.execute(line)
        if on_quit is not None:
            on_quit()
