def hwc_mixed_002_01(self, commands_str):
        """
        update with commands from the block
        """
        commands = dict(parse_qsl(commands_str, keep_blank_values=True))
        _if = commands.get("if", self._if)
        if _if:
            self._if = Condition(_if)
        self._set_int(commands, "max_length")
        self._set_int(commands, "min_length")
        self.color = self._check_color(commands.get("color"))

        self.not_zero = "not_zero" in commands or self.not_zero
        self.show = "show" in commands or self.show
        self.soft = "soft" in commands or self.soft 

def agc_mixed_002_02(data_dir, name, config=None, read_only=False) -> HashStore:
    """
    Create and return a hashStore implementation based on configuration
    """
    if config is None:
        config = {}
    if "type" not in config:
        config["type"] = "memory"
    if config["type"] == "memory":
        return HashStoreMemory(data_dir, name, config, read_only)
    elif config["type"] == "redis":
        return HashStoreRedis(data_dir, name, config, read_only)
    elif config["type"] == "sqlite":
        return HashStoreSqlite(data_dir, name, config, read_only)
    else:
        raise Exception("Unknown hashStore type: " + config["type"]) 

def agc_mixed_002_03(self, ax=None, fontsize=12, **kwargs):
        """
        Plot the AE and the pseudo partial waves.

        Args:
            ax: matplotlib :class:`Axes` or None if a new figure should be created.
            fontsize: fontsize for legends and titles

        Returns: `matplotlib` figure
        """
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()

        ax.set_title(self.name, fontsize=fontsize)
        ax.set_xlabel('$\\omega$', fontsize=fontsize)
        ax.set_ylabel('$\\psi$', fontsize=fontsize)

        ax.plot(self.waves.omega, self.waves.ae, label='AE', **kwargs)
        ax.plot(self.waves.omega, self.waves.pseudo_partial_waves, label='Pseudo partial waves', **kwargs)

        ax.legend(fontsize=fontsize)
        return fig 

def hwc_mixed_002_04(self):
        """return next event or None"""
        if self.event_queue.qsize() == 0:
            return None
        evt = self.event_queue.get()
        while isinstance(evt, win_layout.WinLayout):
            win_layout.set_layout(evt, self.set_layout)
            if self.event_queue.qsize() == 0:
                return None
            evt = self.event_queue.get()
        return evt 

def agc_mixed_002_05(self, msg_id, msg_name):
        """Pop the set of callbacks for a request.

        Return tuple of Nones if callbacks already popped (or don't exist).

        """
        if msg_id not in self._async_callbacks:
            return None, None

        callbacks = self._async_callbacks[msg_id]
        if msg_name not in callbacks:
            return None, None

        callback = callbacks[msg_name]
        del callbacks[msg_name]
        if not callbacks:
            del self._async_callbacks[msg_id]

        return callback, callbacks 

def hwc_mixed_002_06(self):
        """Return keyrange's state as a dict.

        :rtype: dict
        :returns: state of this instance.
        """
        mapping = {}

        if self.start_open:
            mapping["start_open"] = self.start_open

        if self.start_closed:
            mapping["start_closed"] = self.start_closed

        if self.end_open:
            mapping["end_open"] = self.end_open

        if self.end_closed:
            mapping["end_closed"] = self.end_closed

        return mapping
