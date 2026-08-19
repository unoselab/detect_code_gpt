def hwc_mixed_005_01(function):
    """Method decorator caching a method's returned values."""
    cache_variable = '_cached_' + function.__name__
    @wraps(function)
    def function_wrapper(obj, *args, **kwargs):
        # values are cached in a dict stored in the object
        try:
            cache = getattr(obj, cache_variable)
        except AttributeError:
            cache = {}
            setattr(obj, cache_variable, cache)
        args_kwargs = args + tuple(kwargs.values())
        try:
            return cache[args_kwargs]
        except KeyError:
            cache_value = function(obj, *args, **kwargs)
            cache[args_kwargs] = cache_value
            return cache_value
    return function_wrapper 

def agc_mixed_005_02(self, size=None):
        """Draw random samples of the hyperparameters.

        Parameters
        ----------
        size : None, int or array-like, optional
            The number/shape of samples to draw. If None, only one sample is
            returned. Default is None.
        """
        if size is None:
            return {k: v.rvs() if hasattr(v, 'rvs') else v for k, v in self.hyperparams.items()}

        import numpy as np
        samples = []
        num_samples = np.prod(size) if isinstance(size, (list, tuple, np.ndarray)) else size

        for _ in range(int(num_samples)):
            samples.append({k: v.rvs() if hasattr(v, 'rvs') else v for k, v in self.hyperparams.items()})

        if isinstance(size, (list, tuple, np.ndarray)):
            # Reshape the list of dicts into the requested array-like shape
            # This typically returns a numpy array of objects (dicts)
            return np.array(samples).reshape(size)

        return samples 

def hwc_mixed_005_03(env):
    """
    Add Builders and construction variables for C compilers to an Environment.
    """
    static_obj, shared_obj = SCons.Tool.createObjBuilders(env)

    for suffix in CSuffixes:
        static_obj.add_action(suffix, SCons.Defaults.CAction)
        shared_obj.add_action(suffix, SCons.Defaults.ShCAction)
        static_obj.add_emitter(suffix, SCons.Defaults.StaticObjectEmitter)
        shared_obj.add_emitter(suffix, SCons.Defaults.SharedObjectEmitter)

    add_common_cc_variables(env)

    if 'CC' not in env:
        env['CC']    = env.Detect(compilers) or compilers[0]
    env['CFLAGS']    = SCons.Util.CLVar('')
    env['CCCOM']     = '$CC -o $TARGET -c $CFLAGS $CCFLAGS $_CCCOMCOM $SOURCES'
    env['SHCC']      = '$CC'
    env['SHCFLAGS'] = SCons.Util.CLVar('$CFLAGS')
    env['SHCCCOM']   = '$SHCC -o $TARGET -c $SHCFLAGS $SHCCFLAGS $_CCCOMCOM $SOURCES'

    env['CPPDEFPREFIX']  = '-D'
    env['CPPDEFSUFFIX']  = ''
    env['INCPREFIX']  = '-I'
    env['INCSUFFIX']  = ''
    env['SHOBJSUFFIX'] = '.os'
    env['STATIC_AND_SHARED_OBJECTS_ARE_THE_SAME'] = 0

    env['CFILESUFFIX'] = '.c' 

def hwc_mixed_005_04(searchpath, searchtree, dtype = None, default = None):
    """
    Follow searchpath through the datatree in searchtree
    and return if it exists a value of type dtype
    searchpath is a list of keys/indices
    If dtype is None check for any value
    If it is not found return default or if dtype is set to
    a string, list or dict, an empty one
    """
    if is_data_value(searchpath, searchtree, dtype):
        if isinstance(searchpath, (str, unicode, int)):
            searchpath = [searchpath]

        for d in searchpath:
            searchtree = searchtree[d]

    else:
        searchtree = None

    if searchtree == None:
        if default != None:
            return default

        elif dtype in (str, unicode, 'string'):
            return ""

        elif dtype == dict:
            return {}

        elif dtype in (list, tuple, 'list'):
            return []

    return searchtree 

def agc_mixed_005_05(recursive_delay=5, default_duration=10):
    """
    Check the Overpass API status endpoint to determine how long to wait until
    next slot is available.

    Parameters
    ----------
    recursive_delay : int
        how long to wait between recursive calls if server is currently
        running a query
    default_duration : int
        if fatal error, function falls back on returning this value

    Returns
    -------
    pause_duration : int
    """
    import requests

    url = "https://overpass-api.de/api/status"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # The status endpoint provides 'reachable' and 'running' info
        # If the server is busy, it often provides a 'wait' or similar metric
        # based on the specific API response structure.
        if data.get("running"):
            # If running, we check for a suggested wait time or use recursive_delay
            wait_time = data.get("wait", recursive_delay)
            return int(wait_time)

        return 0
    except (requests.RequestException, ValueError, KeyError):
        return default_duration 

def agc_mixed_005_06(self, port_uuid=None, vsiid=None, mgrid=None,
                           typeid=None, typeid_ver=None,
                           vsiid_frmt=vdp_const.VDP_VSIFRMT_UUID,
                           filter_frmt=vdp_const.VDP_FILTER_GIDMACVID,
                           gid=0, mac="", vlan=0, oui=""):
        """Interface function to apps, called for a vNIC DOWN.

        This currently sends an VDP dis-associate message.
        Please refer http://www.ieee802.org/1/pages/802.1bg.html VDP
        Section for more detailed information
        :param uuid: uuid of the vNIC
        :param vsiid: VSI value, Only UUID supported for now
        :param mgrid: MGR ID
        :param typeid: Type ID
        :param typeid_ver: Version of the Type ID
        :param vsiid_frmt: Format of the following VSI argument
        :param filter_frmt: Filter Format. Only <GID,MAC,VID> supported for now
        :param gid: Group ID the vNIC belongs to
        :param mac: MAC Address of the vNIC
        :param vlan: VLAN of the vNIC
        :param oui_id: OUI Type
        :param oui_data: OUI Data
        :param sw_resp: Flag indicating if response is required from the daemon
        """
        # Correct non-zero VLAN needs to be specified
        msg = vdp_const.VDP_MSG_DISASSOCIATE
        payload = {
            'port_uuid': port_uuid,
            'vsiid': vsiid,
            'mgrid': mgrid,
            'typeid': typeid,
            'typeid_ver': typeid_ver,
            'vsiid_frmt': vsiid_frmt,
            'filter_frmt': filter_frmt,
            'gid': gid,
            'mac': mac,
            'vlan': vlan,
            'oui': oui
        }
        return self._send_vdp_message(msg, payload)
