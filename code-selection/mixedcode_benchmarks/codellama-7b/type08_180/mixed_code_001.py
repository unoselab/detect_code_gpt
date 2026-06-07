def hwc_mixed_001_01(p_priority):
    """
    Converts todo.txt priority to an iCalendar priority (RFC 2445).

    Priority A gets priority 1, priority B gets priority 5 and priority C-F get
    priorities 6-9. This scheme makes sure that clients that use "high",
    "medium" and "low" show the correct priority.
    """
    result = 0

    prio_map = {
        'A': 1,
        'B': 5,
        'C': 6,
        'D': 7,
        'E': 8,
        'F': 9,
    }

    try:
        result = prio_map[p_priority]
    except KeyError:
        if p_priority:
            # todos with no priority have priority None, and result of this
            # function will be 0. For all other letters, return 9 (lowest
            # priority in RFC 2445).
            result = 9

    return result 

def agc_mixed_001_02(self, module_or_class):
        """ add new hook specifications defined in the given module_or_class.
        Functions are recognized if they have been decorated accordingly. """
        if isinstance(module_or_class, ModuleType):
            for name in dir(module_or_class):
                if name.startswith('_'):
                    continue
                obj = getattr(module_or_class, name)
                if isinstance(obj, type) and issubclass(obj, HookSpec):
                    self.add_hookspec(obj)
        elif isinstance(module_or_class, type) and issubclass(module_or_class, HookSpec):
            self.add_hookspec(module_or_class)
        else:
            raise TypeError('module_or_class must be a module or a class') 

def hwc_mixed_001_03(self):
    """Remove all pending events without running any."""
    while self.current or self.idlers or self.queue or self.rpcs:
      current = self.current
      idlers = self.idlers
      queue = self.queue
      rpcs = self.rpcs
      _logging_debug('Clearing stale EventLoop instance...')
      if current:
        _logging_debug('  current = %s', current)
      if idlers:
        _logging_debug('  idlers = %s', idlers)
      if queue:
        _logging_debug('  queue = %s', queue)
      if rpcs:
        _logging_debug('  rpcs = %s', rpcs)
      self.__init__()
      current.clear()
      idlers.clear()
      queue[:] = []
      rpcs.clear()
      _logging_debug('Cleared') 

def hwc_mixed_001_04 (self):
        """Write intro comments."""
        self.comment(_("created by %(app)s at %(time)s") %
                    {"app": configuration.AppName,
                     "time": strformat.strtime(self.starttime)})
        self.comment(_("Get the newest version at %(url)s") %
                     {'url': configuration.Url})
        self.comment(_("Write comments and bugs to %(url)s") %
                     {'url': configuration.SupportUrl})
        self.comment(_("Support this project at %(url)s") %
                     {'url': configuration.DonateUrl})
        self.check_date() 

def agc_mixed_001_05(count=4):
    """
    Returns the requested number of boiler plate related items as a list.
    """
    related_items = []
    for i in range(count):
        related_items.append(
            {
                "title": "Related Item {}".format(i),
                "url": "/related-item-{}".format(i),
                "image": {
                    "alt": "Related Item {}".format(i),
                    "url": "/related-item-{}-image.jpg".format(i),
                },
            }
        )
    return related_items 

def agc_mixed_001_06(self, key, section=None, default=_onion_dict_guard):
        """Try to get the key from each dict in turn.
        If you specify the optional section it looks there first.
        """
        if section is not None:
            try:
                return self._dicts[section][key]
            except KeyError:
                pass
        for d in self._dicts:
            try:
                return self._dicts[d][key]
            except KeyError:
                pass
        if default is _onion_dict_guard:
            raise KeyError(key)
        return default
