def agc_mixed_001_01(self):
        r"""Return a :math:`N \rightarrow 2^N` decoder.

        Example Truth Table for a 2:4 decoder:

        .. csv-table::
           :header: :math:`A_1`, :math:`A_0`, \
                    :math:`D_3`, :math:`D_2`, :math:`D_1`, :math:`D_0`
           :stub-columns: 2

           0, 0, 0, 0, 0, 1
           0, 1, 0, 0, 1, 0
           1, 0, 0, 1, 0, 0
           1, 1, 1, 0, 0, 0
        """
        r"""Return a :math:`N \rightarrow 2^N` decoder.

        Example Truth Table for a 2:4 decoder:

        .. csv-table::
           :header: :math:`A_1`, :math:`A_0`, \
                    :math:`D_3`, :math:`D_2`, :math:`D_1`, :math:`D_0`
           :stub-columns: 2

           0, 0, 0, 0, 0, 1
           0, 1, 0, 0, 1, 0
           1, 0, 0, 1, 0, 0
           1, 1, 1, 0, 0, 0
        """, 

def hwc_mixed_001_02(self, property_name):
        """Returns the value associated to the passed property

        This public method is passed a specific property as a string
        and returns the value of that property. If the property is not
        found, None will be returned.

        :param property_name (str) The name of the property
        :return: (str) value for the passed property, or None.
        """
        log = logging.getLogger(self.cls_logger + '.get_value')
        if not isinstance(property_name, basestring):
            log.error('property_name arg is not a string, found type: {t}'.format(t=property_name.__class__.__name__))
            return None
        # Ensure a property with that name exists
        prop = self.get_property(property_name)
        if not prop:
            log.debug('Property name not found matching: {n}'.format(n=property_name))
            return None
        value = self.properties[prop]
        log.debug('Found value for property {n}: {v}'.format(n=property_name, v=value))
        return value 

def hwc_mixed_001_03(self):
    """Cleans up old hunt data from aff4."""

    hunts_ttl = config.CONFIG["DataRetention.hunts_ttl"]
    if not hunts_ttl:
      self.Log("TTL not set - nothing to do...")
      return

    exception_label = config.CONFIG["DataRetention.hunts_ttl_exception_label"]

    hunts_root = aff4.FACTORY.Open("aff4:/hunts", token=self.token)
    hunts_urns = list(hunts_root.ListChildren())

    deadline = rdfvalue.RDFDatetime.Now() - hunts_ttl

    hunts_deleted = 0

    hunts = aff4.FACTORY.MultiOpen(
        hunts_urns, aff4_type=implementation.GRRHunt, token=self.token)
    for hunt in hunts:
      if exception_label in hunt.GetLabelsNames():
        continue

      runner = hunt.GetRunner()
      if runner.context.create_time + runner.context.duration < deadline:
        aff4.FACTORY.Delete(hunt.urn, token=self.token)
        hunts_deleted += 1
        self.HeartBeat()
    self.Log("Deleted %d hunts." % hunts_deleted) 

def agc_mixed_001_04(self, data):
        """ this functions extracts the code, reason from the close body
        if they exists, and if the self.on_close except three arguments """
        # if the on_close callback is "old", just return empty list
        if data is None:
            return None, None
        if not isinstance(data, dict):
            return None, None
        if 'code' in data:
            code = data['code']
        else:
            code = None
        if 'reason' in data:
            reason = data['reason']
        else:
            reason = None
        return code, reason 

def agc_mixed_001_05(self, todays_facts):
        """check if we need to notify user perhaps"""
        if self.user.last_fact_sent is None:
            self.user.last_fact_sent = todays_facts[0]
            self.user.save()
            return True
        else:
            if self.user.last_fact_sent != todays_facts[0]:
                self.user.last_fact_sent = todays_facts[0]
                self.user.save()
                return True
            else:
                return False 

def hwc_mixed_001_06(self):
        # type: () -> bytes
        """
        A method to generate a string representing this El Torito Entry.

        Parameters:
         None.
        Returns:
         String representing this El Torito Entry.
        """
        if not self._initialized:
            raise pycdlibexception.PyCdlibInternalError('El Torito Entry not yet initialized')

        return struct.pack(self.FMT, self.boot_indicator, self.boot_media_type,
                           self.load_segment, self.system_type, 0,
                           self.sector_count, self.load_rba,
                           self.selection_criteria_type,
                           self.selection_criteria)
