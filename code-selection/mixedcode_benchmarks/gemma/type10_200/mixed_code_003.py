def hwc_mixed_003_01(self, pattern):
        # type: (str) -> str
        r"""
        Clean up urlpattern regexes into something readable by humans:

        From:
        > "^(?P<sport_slug>\w+)/athletes/(?P<athlete_slug>\w+)/$"

        To:
        > "{sport_slug}/athletes/{athlete_slug}/"
        """
        # remove optional params
        # TODO(dcramer): it'd be nice to change these into [%s] but it currently
        # conflicts with the other rules because we're doing regexp matches
        # rather than parsing tokens
        result = self._optional_group_matcher.sub(lambda m: "%s" % m.group(1), pattern)

        # handle named groups first
        result = self._named_group_matcher.sub(lambda m: "{%s}" % m.group(1), result)

        # handle non-named groups
        result = self._non_named_group_matcher.sub("{var}", result)

        # handle optional params
        result = self._either_option_matcher.sub(lambda m: m.group(1), result)

        # clean up any outstanding regex-y characters.
        result = (
            result.replace("^", "")
            .replace("$", "")
            .replace("?", "")
            .replace("//", "/")
            .replace("\\", "")
        )

        return result 

def agc_mixed_003_02(env,msvc_version,host_arch,target_arch):
    """
    Find the location of the batch script which should set up the compiler
    for any TARGET_ARCH whose compilers were installed by Visual Studio/VCExpress
    """
    import os
    import glob

    # Common paths for VS installations
    base_paths = [
        os.path.join(env, 'VC', 'vcvarsall.bat'),
        os.path.join(env, 'VC', 'vcvars64.bat'),
        os.path.join(env, 'VC', 'vcvars32.bat'),
    ]

    # Search for vcvarsall.bat in common VS directory structures
    search_patterns = [
        os.path.join(env, 'VC', 'vcvarsall.bat'),
        os.path.join(env, 'VC', 'auxiliary', 'build', 'vcvarsall.bat'),
        os.path.join(env, 'Common7', 'Tools', 'vcvarsall.bat'),
    ]

    for pattern in search_patterns:
        if os.path.exists(pattern):
            return pattern

    # Fallback: search recursively for vcvarsall.bat
    for root, dirs, files in os.walk(env):
        if 'vcvarsall.bat' in files:
            return os.path.join(root, 'vcvarsall.bat')

    return None 

def hwc_mixed_003_03(self):
        """Create a selenium driver using specified config properties

        :returns: a new selenium driver
        :rtype: selenium.webdriver.remote.webdriver.WebDriver
        """
        driver_type = self.config.get('Driver', 'type')
        try:
            if self.config.getboolean_optional('Server', 'enabled'):
                self.logger.info("Creating remote driver (type = %s)", driver_type)
                driver = self._create_remote_driver()
            else:
                self.logger.info("Creating local driver (type = %s)", driver_type)
                driver = self._create_local_driver()
        except Exception as exc:
            error_message = get_error_message_from_exception(exc)
            self.logger.error("%s driver can not be launched: %s", driver_type.capitalize(), error_message)
            raise

        return driver 

def agc_mixed_003_04(restriction=None, connection=None):  # pragma: no cover
    """
    view and kill database connections.
    :param restriction: restriction to be applied to processlist
    :param connection: a datajoint.Connection object. Default calls datajoint.conn()

    Restrictions are specified as strings and can involve any of the attributes of
    information_schema.processlist: ID, USER, HOST, DB, COMMAND, TIME, STATE, INFO.

    Examples:
        dj.kill('HOST LIKE "%compute%"') lists only connections from hosts containing "compute".
        dj.kill('TIME > 600') lists only connections older than 10 minutes.
    """

    import datajoint
    if connection is None:
        connection = datajoint.conn()

    query = "SELECT * FROM information_schema.processlist"
    if restriction:
        query += f" WHERE {restriction}"

    processes = connection.get_results(query)
    if not processes:
        print("No connections found.")
        return

    print(f"{'Id':<10} {'User':<20} {'Host':<20} {'Db':<20} {'Command':<20} {'Time':<10} {'State':<20} {'Info'}")
    print("-" * 120)
    for p in processes:
        print(f"{p['ID']:<10} {p['USER']:<20} {p['HOST']:<20} {p['DB']:<20} {p['COMMAND']:<20} {p['TIME']:<10} {p['STATE']:<20} {p['INFO']}")

    try:
        pid = input("\nEnter Process ID to kill (or press Enter to cancel): ")
        if pid:
            connection.get_results(f"KILL {pid}")
            print(f"Process {pid} killed.")
    except (ValueError, datajoint.OPError) as e:
        print(f"Error killing process: {e}") 

def hwc_mixed_003_05(direction, polygon1, polygon2):
    """Checks if a given ``direction`` is a separating line for two polygons.

    .. note::

       This is a helper for :func:`_polygon_collide`.

    Args:
        direction (numpy.ndarray): A 1D ``2``-array (``float64``) of a
            potential separating line for the two polygons.
        polygon1 (numpy.ndarray): A ``2 x N`` array (``float64``) of ordered
            points in a polygon.
        polygon2 (numpy.ndarray): A ``2 x N`` array (``float64``) of ordered
            points in a polygon.

    Returns:
        bool: Flag indicating if ``direction`` is a separating line.
    """
    # NOTE: We assume throughout that ``norm_squared != 0``. If it **were**
    #       zero that would mean the ``direction`` corresponds to an
    #       invalid edge.
    norm_squared = direction[0] * direction[0] + direction[1] * direction[1]
    params = []
    vertex = np.empty((2,), order="F")
    for polygon in (polygon1, polygon2):
        _, polygon_size = polygon.shape
        min_param = np.inf
        max_param = -np.inf
        for index in six.moves.xrange(polygon_size):
            vertex[:] = polygon[:, index]
            param = cross_product(direction, vertex) / norm_squared
            min_param = min(min_param, param)
            max_param = max(max_param, param)
        params.append((min_param, max_param))
    # NOTE: The indexing is based on:
    #       params[0] = (min_param1, max_param1)
    #       params[1] = (min_param2, max_param2)
    return params[0][0] > params[1][1] or params[0][1] < params[1][0] 

def agc_mixed_003_06(request, abbr):
    """
    Context:
        - metadata
        - chamber
        - chamber_title
        - chamber_select_template
        - chamber_select_collection
        - chamber_select_chambers
        - show_chamber_column
        - abbr
        - legislators
        - sort_order
        - sort_key
        - legislator_table
        - nav_active

    Templates:
        - billy/web/public/legislators.html
        - billy/web/public/chamber_select_form.html
        - billy/web/public/legislator_table.html
    """
    chamber = Chamber.objects.get(abbr=abbr)
    legislators_list = Legislator.objects.filter(chamber=chamber)

    sort_key = request.GET.get('sort', 'last_name')
    sort_order = request.GET.get('order', 'asc')

    if sort_order == 'desc':
        legislators_list = legislators_list.order_by(f'-{sort_key}')
    else:
        legislators_list = legislators_list.order_by(sort_key)

    context = {
        'metadata': {'title': f'Legislators - {chamber.name}'},
        'chamber': chamber,
        'chamber_title': chamber.name,
        'chamber_select_template': 'billy/web/public/chamber_select_form.html',
        'chamber_select_collection': Chamber.objects.all(),
        'chamber_select_chambers': Chamber.objects.all(),
        'show_chamber_column': False,
        'abbr': abbr,
        'legislators': legislators_list,
        'sort_order': sort_order,
        'sort_key': sort_key,
        'legislator_table': 'billy/web/public/legislator_table.html',
        'nav_active': 'legislators',
    }

    return render(request, 'billy/web/public/legislators.html', context)
