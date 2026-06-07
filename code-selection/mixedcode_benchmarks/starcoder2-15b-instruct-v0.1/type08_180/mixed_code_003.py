def agc_mixed_003_01(dspfile, source, env):
    """Generates a Project file based on the version of MSVS that is being used"""

    msvs_version = env['MSVS_VERSION']
    if msvs_version == '8.0':
        project_file = 'Project_VS2005.dsp'
    elif msvs_version == '9.0':
        project_file = 'Project_VS2008.dsp'
    elif msvs_version == '10.0':
        project_file = 'Project_VS2010.dsp'
    elif msvs_version == '11.0':
        project_file = 'Project_VS2012.dsp'
    elif msvs_version == '12.0':
        project_file = 'Project_VS2013.dsp'
    elif msvs_version == '14.0':
        project_file = 'Project_VS2015.dsp'
    elif msvs_version == '15.0':
        project_file = 'Project_VS2017.dsp'
    elif msvs_version == '16.0':
        project_file = 'Project_VS2019.dsp'
    else:
        raise ValueError(f"Unsupported MSVS version: {msvs_version}")
    with open(dspfile, 'w') as f:
        f.write(project_file) 

def agc_mixed_003_02(request):
    """
    Raise :exc:`AssertionError` if gtkmvc3 version is not compatible.

    *request* a dotted string or iterable of string or integers representing the
    minimum version you need. ::

     require("1.0")
     require(("1", "2", "2"))
     require([1,99,0])

    .. note::

       For historical reasons this does not take all API changes into account.
       Some are caught by the argument checks in View and Controller
       constructors.
    """
    if isinstance(request, str):
        request = [int(x) for x in request.split(".")]
    if not isinstance(request, (list, tuple)):
        raise TypeError("request must be a string, list or tuple")
    if len(request)!= 3:
        raise ValueError("request must have exactly 3 components")
    if not all(isinstance(x, int) for x in request):
        raise TypeError("request components must be integers")
    if request[0]!= 1:
        raise ValueError("request major version must be 1")
    if request[1] > 99:
        raise ValueError("request minor version must be less than 100")
    if request[2] < 0:
        raise ValueError("request patch version must be non-negative")
    if request[1] == 99:
        raise AssertionError("gtkmvc3 version 1.99.0 is not compatible") 

def hwc_mixed_003_03(self, obj, item, index):
        """Augment folder listing item
        """
        url = item.get("url")
        title = item.get("Title")

        item["getDownFrom"] = self.localize_date(obj.getDownFrom())
        item["getDownTo"] = self.localize_date(obj.getDownTo())
        item["getValidator"] = obj.getValidator()
        item["replace"]["Title"] = get_link(url, value=title)

        # validation with the most remaining days
        if obj == self.latest_validation:
            item["state_class"] = "state-published"
        # running validations
        elif obj in self.active_validations:
            item["state_class"] = "state-active"
        # inactive validations
        else:
            item["state_class"] = "state-inactive"

        return item 

def agc_mixed_003_04(self, timeout_ms: int = 30000, exception_handler: Callable = None):
        """
        Start a listener greenlet to listen for events in the background.
        Args:
            timeout_ms: How long to poll the Home Server for before retrying.
            exception_handler: Optional exception handler function which can
                be used to handle exceptions in the caller thread.
        """
        def run_listener():
            while True:
                try:
                    self.sync_timeline(timeout_ms=timeout_ms)
                except Exception as e:
                    if exception_handler:
                        exception_handler(e)
                    else:
                        raise e

        self.listener_greenlet = gevent.spawn(run_listener) 

def hwc_mixed_003_05(self, time):
        """
        Set point in time used to check validity of certificates for
        Time can be either python datetime object or number of seconds
        sinse epoch
        """
        if isinstance(time, datetime) or isinstance(time,
                                                             datetime.date):
            seconds = int(time.strftime("%s"))
        elif isinstance(time, int):
            seconds = time
        else:
            raise TypeError("datetime.date, datetime.datetime or integer " +
                            "is required as time argument")
        raise NotImplementedError 

def hwc_mixed_003_06(self, ellipsoid):
        """
        Change the ellipsoid used in the calculation.
        """
        if not isinstance(ellipsoid, (list, tuple)):
            try:
                self.ELLIPSOID = ELLIPSOIDS[ellipsoid]
                self.ellipsoid_key = ellipsoid
            except KeyError:
                raise Exception(
                    "Invalid ellipsoid. See geopy.distance.ELIPSOIDS"
                )
        else:
            self.ELLIPSOID = ellipsoid
            self.ellipsoid_key = None
        return
