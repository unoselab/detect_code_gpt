def hwc_mixed_004_01(self, id=None, application=None, name=None, revision=None, environment=None, parameters=None, submodules=None, destroyInterval=None):
        """ Smart method. It does everything, to return Instance with given parameters within the application.
        If instance found running and given parameters are actual: return it.
        If instance found, but parameters differs - reconfigure instance with new parameters.
        If instance not found: launch instance with given parameters.
        Return: Instance object.
        """
        instance = self.get_or_create_instance(id, application, revision, environment, name, parameters, submodules, destroyInterval)

        reconfigure = False
        # if found:
        #     if revision and revision is not found.revision:
        #         reconfigure = True
        #     if parameters and parameters is not found.parameters:
        #         reconfigure = True

        # We need to reconfigure instance
        if reconfigure:
            instance.reconfigure(revision=revision, parameters=parameters)

        return instance 

def hwc_mixed_004_02(self, id):
        """PUT /mapfiles/id: Update an existing item."""
        map = self._get_map_from_user_by_id(c.user, id)
        if map is None:
            abort(404)

        # get json content from PUT request
        content = request.environ['wsgi.input'].read(int(request.environ['CONTENT_LENGTH']))
        #content = content.decode('utf8')

        # update mapfile
        mapfile = Mapfile()
        dict = simplejson.loads(content)
        mapfile.from_dict(dict)
        mapfile.to_file(os.path.join(config['mapfiles_dir'], map.filepath))
        if mapfile.get_name() != map.name:
            self._update_map(map, name=mapfile.get_name())

        response.status = 201
        return 

def agc_mixed_004_03(i):
    """
    Input:  {
              path               - path to be locked

              (get_lock)         - if 'yes', lock this entry
              (lock_retries)     - number of retries to aquire lock (default=11)
              (lock_retry_delay) - delay in seconds before trying to aquire lock again (default=3)
              (lock_expire_time) - number of seconds before lock expires (default=30)

              (unlock_uid)       - UID of the lock to release it
            }

    Output: {
              return       - return code =  0, if successful
                                         = 32, couldn't acquire lock (still locked after all retries)
                                         >  0, if error
              (error)      - error text if return > 0

              (lock_uid)   - lock UID, if locked successfully
            }
    """
    if i.get('get_lock') == 'yes':
        for _ in range(i.get('lock_retries', 11)):
            if acquire_lock(i['path']):
                return {'return': 0, 'lock_uid':'some_lock_uid'}
            time.sleep(i.get('lock_retry_delay', 3))
        return {'return': 32, 'error': 'Could not acquire lock'}
    elif i.get('unlock_uid'):
        if release_lock(i['path'], i['unlock_uid']):
            return {'return': 0}
        else:
            return {'return': 1, 'error': 'Could not release lock'}
    else:
        return {'return': 1, 'error': 'Invalid input'} 

def agc_mixed_004_04(python_modules, callback, ignore=tuple()):
    """
    Recursively scans `python_modules` for providers registered with
    :py:mod:`wiring.scanning.register` module and for each one calls `callback`
    with :term:`specification` as the first argument, and the provider object
    as the second.

    Each element in `python_modules` may be a module reference or a string
    representing a path to a module.

    Module paths given in `ignore` are excluded from scanning.
    """
    for module_path in python_modules:
        if module_path in ignore:
            continue
        if isinstance(module_path, str):
            module = sys.modules.get(module_path, None)
            if module is None:
                module = __import__(module_path)
        else:
            module = module_path
        for name, obj in inspect.getmembers(module):
            if hasattr(obj, "__wiring_specification__"):
                callback(obj.__wiring_specification__, obj) 

def agc_mixed_004_05(self, command, ignore_errors=None):
        """ Call remote command with logging. """
        if ignore_errors is None:
            ignore_errors = self.ignore_errors
        try:
            output = self.run_command(command)
        except Exception as e:
            if ignore_errors:
                self.logger.warning(f"Failed to execute command: {command}. Error: {e}")
                return None
            else:
                raise e
        self.logger.debug(f"Command output: {output}")
        return output 

def hwc_mixed_004_06(self, cont):
        """Performs #{}-interpolation.  The result is always treated as a fixed
        syntactic unit and will not be re-evaluated.
        """
        # TODO that's a lie!  this should be in the parser for most cases.
        if not isinstance(cont, six.string_types):
            warn(FutureWarning(
                "do_glob_math was passed a non-string {0!r} "
                "-- this will no longer be supported in pyScss 2.0"
                .format(cont)
            ))
            cont = six.text_type(cont)
        if '#{' not in cont:
            return cont
        cont = _expr_glob_re.sub(self._pound_substitute, cont)
        return cont
