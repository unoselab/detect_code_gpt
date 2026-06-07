def hwc_mixed_003_01():
    """
    Run lint command in the shell and save results to lint-result.xml
    """
    lint, app_dir, lint_result, ignore_layouts = parse_args()
    if not lint_result:
        if not distutils.spawn.find_executable(lint):
            raise Exception(
                '`%s` executable could not be found and path to lint result not specified. See --help' % lint)
        lint_result = os.path.join(app_dir, 'lint-result.xml')
        call_result = subprocess.call([lint, app_dir, '--xml', lint_result])
        if call_result > 0:
            print('Running the command failed with result %s. Try running it from the console.'
                  ' Arguments for subprocess.call: %s' % (call_result, [lint, app_dir, '--xml', lint_result]))
    else:
        if not os.path.isabs(lint_result):
            lint_result = os.path.join(app_dir, lint_result)
    lint_result = os.path.abspath(lint_result)
    return lint_result, app_dir, ignore_layouts 

def agc_mixed_003_02(cls, sock):
    """Parse the request (the pre-execution) section of the nailgun protocol from the given socket.

    Handles reading of the Argument, Environment, Working Directory and Command chunks from the
    client which represents the "request" phase of the exchange. Working Directory and Command are
    required and must be sent as the last two chunks in this phase. Argument and Environment chunks
    are optional and can be sent more than once (thus we aggregate them).
    """

    arg_chunk = cls.read_chunk(sock)
    if arg_chunk is None:
        return None

    # Read the environment chunk
    env_chunk = cls.read_chunk(sock)
    if env_chunk is None:
        return None

    # Read the working directory chunk
    cwd_chunk = cls.read_chunk(sock)
    if cwd_chunk is None:
        return None

    # Read the command chunk
    cmd_chunk = cls.read_chunk(sock)
    if cmd_chunk is None:
        return None

    # Read the remaining chunks (if any)
    chunks = []
    while True:
        chunk = cls.read_chunk(sock)
        if chunk is None:
            break
        chunks.append(chunk)

    # Return the parsed request
    return cls(arg_chunk, env_chunk, cwd_chunk, cmd_chunk, chunks) 

def hwc_mixed_003_03(self, ip_addr):
        """
        Do reverse lookup on an ip address
        """
        # Handle silly fake ipv6 addresses
        try:
            if ip_addr[:7] == '::ffff:':
                ip_addr = ip_addr[7:]
        except TypeError:
            pass

        if ip_addr[0] in string.letters:
            return ip_addr

        try:
            return self.hostsmap[ip_addr]
        except KeyError:
            pass

        try:
            name = socket.gethostbyaddr(ip_addr)[0]
        except socket.error:
            name = ip_addr

        self.hostsmap[ip_addr] = name
        return name 

def agc_mixed_003_04(header, required_fields=None):
    """validate_header ensures that the first row contains the exp_id,
       var_name, var_value, and token. Capitalization isn't important, but
       ordering is. This criteria is very strict, but it's reasonable
       to require.

       Parameters
       ==========
       header: the header row, as a list
       required_fields: a list of required fields. We derive the required
                        length from this list.

       Does not return, instead exits if malformed. Runs silently if OK.

    """
    if len(header)!= 4:
        raise ValueError("Header must have 4 fields")

    # Check that the header is in the right order
    if header[0].lower()!= "exp_id":
        raise ValueError("Header must have exp_id as the first field")
    if header[1].lower()!= "var_name":
        raise ValueError("Header must have var_name as the second field")
    if header[2].lower()!= "var_value":
        raise ValueError("Header must have var_value as the third field")
    if header[3].lower()!= "token":
        raise ValueError("Header must have token as the fourth field")

    # Check that the required fields are present
    if required_fields is not None:
        for field in required_fields:
            if field not in header:
                raise ValueError("Header must have %s as a field" % field) 

def agc_mixed_003_05(self, event, grid):
        """saves any editing of the grid but does not continue to the next window"""
        self.save_grid(grid)
        self.save_grid_button.Hide()
        self.save_grid_button.SetLabel("Save")
        self.save_grid_button.SetBackgroundColour("white")
        self.save_grid_button.SetForegroundColour("black")
        self.save_grid_button.SetFont(wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD))
        self.save_grid_button.SetToolTip(wx.ToolTip("Save the grid"))
        self.save_grid_button.Bind(wx.EVT_BUTTON, self.on_saveButton, grid)
        self.save_grid_button.Bind(wx.EVT_ENTER_WINDOW, self.on_saveButton_enter, grid)
        self.save_grid_button.Bind(wx.EVT_LEAVE_WINDOW, self.on_saveButton_leave, grid)
        self.save_grid_button.Bind(wx.EVT_LEFT_DOWN, self.on_saveButton_click, grid)
        self.save_grid_button.Bind(wx.EVT_LEFT_DCLICK, self.on_saveButton_click, grid)
        self.save_grid_button.Bind(wx.EVT_LEFT_UP, self.on_saveButton_click, grid)
        self.save_grid_button.Bind(wx.EVT_RIGHT_DOWN, self.on_saveButton_click, grid)
        self.save_grid_button.Bind(wx.EVT_RIGHT_DCLICK, self.on_saveButton_click, grid)
        self.save_grid_button.Bind(wx.EVT_RIGHT_UP, self.on_saveButton_click, grid)
        self.save_grid_button.Bind(wx.EVT_MOTION, self.on_saveButton_motion, grid)
        self.save_grid_button.Bind(wx.EVT_MOUSEWHEEL, self.on_saveButton_mousewheel, grid)
        self.save_grid_button.Bind(wx.EVT_KEY_DOWN, self.on_saveButton_keydown, grid)
        self.save_grid_button.Bind(wx.EVT_KEY_UP, self.on_saveButton_keyup, grid)
        self.save_grid_ 

def hwc_mixed_003_06(opaque, conn, data):
    """
    Convenience function adding common data to the event and sending it
    on the salt event bus.

    :param opaque: the opaque data that is passed to the callback.
                   This is a dict with 'prefix', 'object' and 'event' keys.
    :param conn: libvirt connection
    :param data: additional event data dict to send
    """
    tag_prefix = opaque['prefix']
    object_type = opaque['object']
    event_type = opaque['event']

    # Prepare the connection URI to fit in the tag
    # qemu+ssh://user@host:1234/system -> qemu+ssh/user@host:1234/system
    uri = urlparse(conn.getURI())
    uri_tag = [uri.scheme]
    if uri.netloc:
        uri_tag.append(uri.netloc)
    path = uri.path.strip('/')
    if path:
        uri_tag.append(path)
    uri_str = "/".join(uri_tag)

    # Append some common data
    all_data = {
        'uri': conn.getURI()
    }
    all_data.update(data)

    tag = '/'.join((tag_prefix, uri_str, object_type, event_type))

    # Actually send the event in salt
    if __opts__.get('__role') == 'master':
        salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event(all_data, tag)
    else:
        __salt__['event.send'](tag, all_data)
