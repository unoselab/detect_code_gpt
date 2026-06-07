def hwc_mixed_003_01(self, service_id, workers):
        """Reconfigure a service registered in ServiceManager

        :param service_id: the service id
        :type service_id: uuid.uuid4
        :param workers: number of processes/workers for this service
        :type workers: int
        :raises: ValueError
        """
        try:
            sc = self._services[service_id]
        except KeyError:
            raise ValueError("%s service id doesn't exists" % service_id)
        else:
            _utils.check_workers(workers, minimum=(1 - sc.workers))
            sc.workers = workers
            # Reset forktimes to respawn services quickly
            self._forktimes = [] 

def agc_mixed_003_02(self, recarr, date_range):
        """ Given a recarr, slice out the given artic.date.DateRange if a
        datetime64 index exists """
        if not isinstance(recarr, np.ndarray):
            recarr = np.array(recarr)
        if recarr.dtype.kind == 'M':
            if date_range is None:
                return recarr
            else:
                return recarr[date_range]
        else:
            return recarr 

def hwc_mixed_003_03(self, struct):
        """
        unpacks the given struct from the underlying buffer and returns
        the results. Will raise an UnpackException if there is not
        enough data to satisfy the format of the structure
        """

        size = struct.size

        offset = self.offset
        if self.data:
            avail = len(self.data) - offset
        else:
            avail = 0

        if avail < size:
            raise UnpackException(struct.format, size, avail)

        self.offset = offset + size
        return struct.unpack_from(self.data, offset) 

def hwc_mixed_003_04(self, organisation_id, role):
        """Check the user's role for the organisation"""
        if organisation_id is None:
            return False

        try:
            org = self.organisations.get(organisation_id, {})
            user_role = org.get('role')
            state = org.get('state')
        except AttributeError:
            return False

        return user_role == role.value and state == State.approved.name 

def agc_mixed_003_05( module ):
        """
        Generates HTML information to display for the about info for a module.

        :param      module  | <module>
        """
        return """
        <div class="module-info">
            <div class="module-info-header">
                <h3>%s</h3>
            </div>
            <div class="module-info-body">
                <p>%s</p>
            </div>
        </div>
        """ % (module.__name__, module.__doc__) 

def agc_mixed_003_06(parser, dest, arguments=set(), default=None,
                         single_arg=False, required=False):
        """Adds mutually exclusive switch arguments.

        Args:
            arguments: a dictionary that maps switch name to helper text. Use
                sets to skip help texts.
        """

        if not isinstance(arguments, dict):
            raise TypeError('arguments must be a dictionary')
        if not isinstance(default, (type(None), str)):
            raise TypeError('default must be a string or None')
        if not isinstance(single_arg, bool):
            raise TypeError('single_arg must be a boolean')
        if not isinstance(required, bool):
            raise TypeError('required must be a boolean')
