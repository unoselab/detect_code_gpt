def agc_mixed_004_01(config, ret, repo):
    """
    Parse image log strings into grokable data
    """
    if not ret:
        return

    for image in ret:
        image_name = image['name']
        image_log = image['log']
        image_log_lines = image_log.split('\n')
        image_log_lines = [line for line in image_log_lines if line]
        image_log_lines = [line.strip() for line in image_log_lines]

        image_multilogs = []
        for line in image_log_lines:
            image_multilogs.append({
                'log': line,
                'repo': repo,
                'name': image_name,
            })

        ret[image_name]['multilogs'] = image_multilogs 

def hwc_mixed_004_02(self, memberName, accessorName, classNamingConvention):
        """
    :type memberName: str
    :type accessorName: str
    :type classNamingConvention: INamingConvention|None
"""        
        # Using user's custom getter or setter name.
        customAccessorName = self._accessorNameDict[accessorName]
        if customAccessorName is not None:
            return customAccessorName

        # If the class has a custom naming convention, we use it. Cf. 'namingConvention' decorator.
        # Otherwise, we use the member's naming convention, camelCase or underscore depending on the decorator that was used
        # (respectively synthesizeMember or synthesize_member).
        namingConvention = self._namingConvention
        if classNamingConvention is not None:
            namingConvention = classNamingConvention

        # @hack: I don't much like that...
        methodName = self._NAMING_CONVENTION_ACCESSOR_NAME_METHOD_DICT[accessorName]
        # Using naming convention to transform member's name to an accessor name.
        return getattr(namingConvention, methodName)(memberName) 

def agc_mixed_004_03(job, job_vars):
    """
    Upload bam to S3. Requires S3AM and a ~/.boto config file.
    """
    import os
    import subprocess
    import sys
    import tempfile

    # Get the bam file from the job_vars
    bam_file = job_vars['bam_file']

    # Get the bucket from the job_vars
    bucket = job_vars['bucket']

    # Get the s3_key from the job_vars
    s3_key = job_vars['s3_key']

    # Get the s3_key_prefix from the job_vars
    s3_key_prefix = job_vars['s3_key_prefix']

    # Get the s3_key_suffix from the job_vars
    s3_key_suffix = job_vars['s3_key_suffix']

    # Get the s3_key_suffix_prefix from the job_vars
    s3_key_suffix_prefix = job_vars['s3_key_suffix_prefix']

    # Get the s3_key_suffix_suffix from the job_vars
    s3_key_suffix_suffix = job_vars['s3_key_suffix_suffix']

    # Get the s3_key_suffix_suffix_prefix from the job_vars
    s3_key_suffix_suffix_prefix = job_vars['s3_key_suffix_suffix_prefix']

    # Get the s3_key_suffix_suffix_suffix from the job_vars
    s3_key_suffix_suffix_suffix = job_vars['s3_key_suffix_suffix_suffix']

    # Get the s3_key_suffix_suffix_suffix_prefix from the job_vars
    s3_key_suffix_suffix_suffix_prefix = job_vars['s3_key_suffix_suffix_suffix_prefix']

    # Get the s3_key_suffix_suffix_suffix_suffix 

def agc_mixed_004_04(self):
        """ Consume commands from the queue.

        The command is repeated according to the configured value.
        Wait after each command is sent.

        The bridge socket is a shared resource. It must only
        be used by one thread at a time. Note that this can and
        will delay commands if multiple groups are attempting
        to communicate at the same time on the same bridge.
        """
        while not self.stopped.is_set():
            try:
                command = self.queue.get(timeout=1)
            except Empty:
                continue

            if command is None:
                break

            self.logger.debug('Sending command: %s', command)
            self.bridge.send(command)
            self.bridge.recv()

            if self.repeat:
                self.logger.debug('Waiting %s seconds', self.repeat)
                time.sleep(self.repeat) 

def hwc_mixed_004_05(self, on_quit=None):
        """
        Reads the standard input until the shell session is stopped

        :param on_quit: A call back method, called without argument when the
                        shell session has ended
        """
        # Start the init script
        self._run_script(
            self.__session, self._context.get_property(PROP_INIT_FILE)
        )

        # Run the script
        script_file = self._context.get_property(PROP_RUN_FILE)
        if script_file:
            self._run_script(self.__session, script_file)
        else:
            # No script: run the main loop (blocking)
            self._run_loop(self.__session)

        # Nothing more to do
        self._stop_event.set()
        sys.stdout.write("Bye !\n")
        sys.stdout.flush()
        if on_quit is not None:
            # Call a handler if needed
            on_quit() 

def hwc_mixed_004_06(self):
        """Initializes a connection to the smtp server

        :return: True on success, False otherwise
        """
        connection_method = 'SMTP_SSL' if self.ssl else 'SMTP'
        self._logger.debug('Trying to connect via {}'.format(connection_method))
        smtp = getattr(smtplib, connection_method)
        if self.port:
            self._smtp = smtp(self.address, self.port)
        else:
            self._smtp = smtp(self.address)
        self._smtp.ehlo()
        if self.tls:
            self._smtp.starttls()
            self._smtp.ehlo()
        self._logger.info('Got smtp connection')
        if self.username and self.password:
            self._logger.info('Logging in')
            self._smtp.login(self.username, self.password)
        self._connected = True
