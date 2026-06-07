def agc_mixed_001_01(name, master, ticket):
    """
    Setup the icinga2 node.

    name
        The domain name for which this certificate will be saved

    master
        Icinga2 master node for which this certificate will be saved

    ticket
        Authentication ticket generated on icinga2 master
    """
    os.makedirs(os.path.join(config.icinga2.pki_dir, name))

    # Create the certificate
    cmd = [
        "icinga2",
        "node",
        "setup",
        "--pki-dir",
        config.icinga2.pki_dir,
        "--pki-name",
        name,
        "--master",
        master,
        "--ticket",
        ticket,
    ]
    subprocess.check_call(cmd) 

def hwc_mixed_001_02(self):
        """
        save the cache index, in case it was modified.

        Saves the index table and the file name repository in the file
        `index.dat`
        """

        if self.__modified_flag:
            self.__filename_rep.update_id_counter()
            indexfilename = os.path.join(self.__dir, "index.dat")
            self._write_file(
                indexfilename,
                (self.__index,
                 self.__filename_rep))

            self.__modified_flag = False 

def hwc_mixed_001_03(self, value):
        """Decide whether a given value should be collected."""
        return (
            # decorated with @transition
            isinstance(value, TransitionWrapper)
            # Relates to a compatible transition
            and value.trname in self.workflow.transitions
            # Either not bound to a state field or bound to the current one
            and (not value.field or value.field == self.state_field)) 

def hwc_mixed_001_04(self, dt):
        """
        Given a dt, find that day's close and period start (close - offset).
        """
        period_end = self.cal.open_and_close_for_session(
            self.cal.minute_to_session_label(dt),
        )[1]

        # Align the market close time here with the execution time used by the
        # simulation clock. This ensures that scheduled functions trigger at
        # the correct times.
        self._period_end = self.cal.execution_time_from_close(period_end)

        self._period_start = self._period_end - self.offset
        self._period_close = self._period_end 

def agc_mixed_001_05(self, target, callback = None, name = None, complete = None, *args, **kargs):
        """
        Start task.
        @target: callable to run with *args and **kargs arguments.
        @callback: callable executed after target.
        @name: thread name
        @complete: complete executed after target in finally
        """
        if self.running:
            raise RuntimeError("Already running")
        self.running = True
        self.target = target
        self.callback = callback
        self.complete = complete
        self.name = name
        self.args = args
        self.kargs = kargs
        self.thread = threading.Thread(target = self.run_task, name = name)
        self.thread.start() 

def agc_mixed_001_06(name='default', **kwargs):
    """
    Request power state change

    name = ``default``
        * network -- Request network boot
        * hd -- Boot from hard drive
        * safe -- Boot from hard drive, requesting 'safe mode'
        * optical -- boot from CD/DVD/BD drive
        * setup -- Boot into setup utility
        * default -- remove any IPMI directed boot device request

    kwargs
        - api_host=localhost
        - api_user=admin
        - api_pass=
        - api_port=623
        - api_kg=None
    """
    if name == 'default':
        return None
    elif name == 'network':
        return 'network'
    elif name == 'hd':
        return 'hd'
    elif name =='safe':
        return'safe'
    elif name == 'optical':
        return 'optical'
    elif name =='setup':
        return'setup'
    else:
        raise ValueError('Invalid boot device name: %s' % name)
