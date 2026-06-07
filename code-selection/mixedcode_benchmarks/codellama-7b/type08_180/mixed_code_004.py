async def agc_mixed_004_01(app, loop):
    """Sends a message to the webhook channel when server starts."""
    global bot
    bot = app.bot
    global webhook_channel
    webhook_channel = app.config['WEBHOOK_CHANNEL']
    global webhook_url
    webhook_url = app.config['WEBHOOK_URL']
    global webhook_message
    webhook_message = app.config['WEBHOOK_MESSAGE']
    global webhook_embed
    webhook_embed = app.config['WEBHOOK_EMBED']
    global webhook_embed_title
    webhook_embed_title = app.config['WEBHOOK_EMBED_TITLE']
    global webhook_embed_description
    webhook_embed_description = app.config['WEBHOOK_EMBED_DESCRIPTION']
    global webhook_embed_color
    webhook_embed_color = app.config['WEBHOOK_EMBED_COLOR']
    global webhook_embed_footer
    webhook_embed_footer = app.config['WEBHOOK_EMBED_FOOTER']
    global webhook_embed_footer_icon_url
    webhook_embed_footer_icon_url = app.config['WEBHOOK_EMBED_FOOTER_ICON_URL']
    global webhook_embed_thumbnail
    webhook_embed_thumbnail = app.config['WEBHOOK_EMBED_THUMBNAIL']
    global webhook_embed_image
    webhook_embed_image = app.config['WEBHOOK_EMBED_IMAGE']
    global webhook_embed_author
    webhook_embed_author = app.config['WEBHOOK_EMBED_AUTHOR']
    global webhook_embed_author_name
    webhook_embed_author_name = app.config['WEBHOOK_EMBED_AUTHOR_NAME']
    global webhook_embed_author_url
    webhook_embed_author_url = app.config['WEBHOOK_EMBED_AUTHOR_URL']
    global webhook_embed_author_icon_url
    webhook 

def agc_mixed_004_02(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a virtual network.

    :param name: The name of the virtual network to delete.

    :param resource_group: The resource group name assigned to the
        virtual network

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.virtual_network_delete testnet testgroup

    """
    conn = await hub.exec.azurerm.utils.get_client(
        ctx, "network", **kwargs
    )
    try:
        vnet = await hub.exec.azurerm.utils.get_by_name(
            ctx, conn.virtual_networks.get, resource_group, name
        )
        await hub.exec.azurerm.utils.delete_parent(
            ctx, vnet, "virtual_networks.delete", **kwargs
        )
        if kwargs.get("delete_parent_resources", True):
            await hub.exec.azurerm.utils.delete_parent_resources(
                ctx, vnet, **kwargs
            )
    except CloudError as exc:
        await hub.exec.azurerm.utils.log_cloud_error("network", str(exc), **kwargs)
        raise

    return True 

def hwc_mixed_004_03(self, targets: sos_targets):
        """Trim DAG to keep only nodes that produce targets"""
        if 'DAG' in env.config['SOS_DEBUG'] or 'ALL' in env.config['SOS_DEBUG']:
            env.log_to_file('DAG', 'create subgraph')
        # first, find all nodes with targets
        subnodes = []
        for node in self.nodes():
            if node._output_targets.valid() and any(
                    x in node._output_targets for x in targets):
                subnodes.append(node)
        #
        ancestors = set()
        for node in subnodes:
            ancestors |= nx.ancestors(self, node)
        return SoS_DAG(nx.subgraph(self, subnodes + list(ancestors))) 

def agc_mixed_004_04(msg):
    """
    Communication with the Pageant process is done through a shared
    memory-mapped file.
    """
    pageant_path = os.path.join(os.environ['ProgramFiles'], 'PuTTY', 'pageant.exe')
    pageant_handle = ctypes.windll.kernel32.OpenFileMappingW(
        ctypes.wintypes.DWORD(0x4),
        ctypes.wintypes.BOOL(0),
        ctypes.wintypes.LPCWSTR(pageant_path)
    )
    if not pageant_handle:
        raise Exception('Could not open pageant')
    pageant_buffer = ctypes.windll.kernel32.MapViewOfFile(
        pageant_handle,
        ctypes.wintypes.DWORD(0xF001F),
        ctypes.wintypes.DWORD(0),
        ctypes.wintypes.DWORD(0),
        ctypes.wintypes.SIZE_T(ctypes.sizeof(ctypes.c_uint32))
    )
    if not pageant_buffer:
        raise Exception('Could not map pageant buffer')
    try:
        pageant_buffer.contents.value = msg
        ctypes.windll.kernel32.FlushViewOfFile(pageant_buffer, ctypes.sizeof(ctypes.c_uint32))
        ctypes.windll.kernel32.UnmapViewOfFile(pageant_buffer)
    finally:
        ctypes.windll.kernel32.CloseHandle(pageant_handle) 

def hwc_mixed_004_05(self, type, nationality=None, gender=None,
                             firstletter=None, orderby='view-week-count',
                             page=1, count=20):
        """doc: http://open.youku.com/docs/docs?id=89
        """
        url = 'https://openapi.youku.com/v2/persons/by_type.json'
        params = {
            'client_id': self.client_id,
            'type': type,
            'nationality': nationality,
            'gender': gender,
            'firstletter': firstletter,
            'orderby': orderby,
            'page': page,
            'count': count
        }
        params = remove_none_value(params)
        r = requests.get(url, params=params)
        check_error(r)
        return r.json() 

def hwc_mixed_004_06(self):
        """
        Unregisters all bundle services
        """
        # Copy the services list, as it will be modified during the process
        with self.__registration_lock:
            registered_services = self.__registered_services.copy()

        for registration in registered_services:
            try:
                registration.unregister()
            except BundleException:
                # Ignore errors at this level
                pass

        if self.__registered_services:
            _logger.warning("Not all services have been unregistered...")

        with self.__registration_lock:
            # Clear the list, just to be clean
            self.__registered_services.clear()
