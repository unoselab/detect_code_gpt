def agc_mixed_002_01(peer_interface, user, paths=None, verbose=False, cmd=None,
                  gid=None, fatal=False):
    """Sync all hosts to an specific path

    The type of group is integer, it allows user has permissions to
    operate a directory have a different group id with the user id.

    Propagates exception if any operation fails and fatal=True.
    """
    if not paths:
        paths = []

    if not isinstance(paths, list):
        paths = [paths]

    if not cmd:
        cmd = 'rsync -a --delete --exclude=.git --exclude=.gitignore'

    if gid:
        cmd += ' --group=%s' % gid

    if verbose:
        cmd += ' -v'

    cmd += ' %s %s@%s:%s' % (paths, user, peer_interface, paths)

    if verbose:
        print(cmd)

    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        if fatal:
            raise e
        else:
            print('%s failed' % cmd) 

def agc_mixed_002_02(self, bg=None):
        """Return a unique identifier for the background data"""
        if bg is None:
            bg = self.bg
        if bg is None:
            return None
        if isinstance(bg, str):
            return bg
        if isinstance(bg, dict):
            return tuple(sorted(bg.items()))
        if isinstance(bg, list):
            return tuple(sorted(bg))
        if isinstance(bg, tuple):
            return bg
        if isinstance(bg, np.ndarray):
            return tuple(sorted(bg.tolist()))
        raise ValueError("Unknown type for background data") 

def hwc_mixed_002_03(self, result):
        """Fix indentation undistinguish from the next logical line."""
        num_indent_spaces = int(result['info'].split()[1])
        line_index = result['line'] - 1
        target = self.source[line_index]

        spaces_to_add = num_indent_spaces - len(_get_indentation(target))
        indent = len(_get_indentation(target))
        modified_lines = []

        while len(_get_indentation(self.source[line_index])) >= indent:
            self.source[line_index] = (' ' * spaces_to_add +
                                       self.source[line_index])
            modified_lines.append(1 + line_index)  # Line indexed at 1.
            line_index -= 1

        return modified_lines 

def agc_mixed_002_04(self, request):
        """Handle an HTTP request for executing an API call.

        This method authenticates the request checking its signature, and then
        calls the C{execute} method, passing it a L{Call} object set with the
        principal for the authenticated user and the generic parameters
        extracted from the request.

        @param request: The L{HTTPRequest} to handle.
        """
        signature = request.args.get('signature', [None])[0]
        if not signature:
            raise HTTPBadRequest('Missing signature parameter')
        if not self.checkSignature(request, signature):
            raise HTTPUnauthorized('Invalid signature')

        # Extract the parameters
        parameters = {}
        for key in request.args:
            if key != 'signature':
                parameters[key] = request.args[key][0]

        # Execute the call
        call = Call(self.principal, parameters)
        self.execute(call)

        # Return the result
        return self.response(call) 

def hwc_mixed_002_05(hostname, timeout=20, username=None, password=None):
    """
    Connect to the Dell DRAC and have the boot order set to PXE
    and power cycle the system to PXE boot

    CLI Example:

    .. code-block:: bash

        salt-run drac.pxe example.com
    """
    _cmds = [
        'racadm config -g cfgServerInfo -o cfgServerFirstBootDevice pxe',
        'racadm config -g cfgServerInfo -o cfgServerBootOnce 1',
        'racadm serveraction powercycle',
    ]

    client = __connect(hostname, timeout, username, password)

    if isinstance(client, paramiko.SSHClient):
        for i, cmd in enumerate(_cmds, 1):
            log.info('Executing command %s', i)

            (stdin, stdout, stderr) = client.exec_command(cmd)

        if 'successful' in stdout.readline():
            log.info('Executing command: %s', cmd)
        else:
            log.error('Unable to execute: %s', cmd)
            return False

    return True 

def hwc_mixed_002_06(name, dir_tmp):
    """
    Opens up json file, invokes doi_resolver, closes file, updates changelog, cleans directory, and makes new bag.
    :param str name: Name of current .lpd file
    :param str dir_tmp: Path to tmp directory
    :return none:
    """
    logger_doi_main.info("enter process_lpd")
    dir_root = os.getcwd()
    dir_bag = os.path.join(dir_tmp, name)
    dir_data = os.path.join(dir_bag, 'data')

    # Navigate down to jLD file
    # dir : dir_root -> dir_data
    os.chdir(dir_data)

    # Open jld file and read in the contents. Execute DOI Resolver.
    jld_data = read_json_from_file(os.path.join(dir_data, name + '.jsonld'))

    # Overwrite data with new data
    jld_data = DOIResolver(dir_root, name, jld_data).main()
    # Open the jld file and overwrite the contents with the new data.
    write_json_to_file(jld_data)

    # Open changelog. timestamp it. Prompt user for short description of changes. Close and save
    # update_changelog()

    # Delete old bag files, and move files to bag root for re-bagging
    # dir : dir_data -> dir_bag
    dir_cleanup(dir_bag, dir_data)
    finish_bag(dir_bag)

    logger_doi_main.info("exit process_lpd")
    return
