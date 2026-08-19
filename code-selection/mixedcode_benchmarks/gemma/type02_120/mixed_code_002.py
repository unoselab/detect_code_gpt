def agc_mixed_002_01(self):
        """Simulated time series"""
        import numpy as np
        import pandas as pd

        n_points = 100
        time = np.arange(n_points)
        trend = 0.1 * time
        seasonal = 10 * np.sin(2 * np.pi * time / 12)
        noise = np.random.normal(0, 2, n_points)

        series = trend + seasonal + noise
        return pd.Series(series, index=pd.date_range(start='2020-01-01', periods=n_points, freq='M')) 

async def agc_mixed_002_02(coros, display, *, verbose):
    """The tricky thing about running multiple coroutines in parallel is what
    we're supposed to do when one of them raises an exception. The approach
    we're using here is to catch exceptions and keep waiting for other tasks to
    finish. At the end, we reraise a GatheredExceptions error, if any
    exceptions were caught.

    Another minor detail: We also want to make sure to start coroutines in the
    order given, so that they end up appearing to the user alphabetically in
    the fancy display. Note that asyncio.gather() puts coroutines in a set
    internally, so we schedule coroutines *before* we give them to gather().
    """

    import asyncio

    tasks = [asyncio.create_task(c) for c in coros]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    exceptions = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            exceptions.append(res)
            if verbose:
                display.log(f"Task {i} failed: {res}")

    if exceptions:
        raise GatheredExceptions(exceptions)

    return results 

def hwc_mixed_002_03(filesystem, registries):
    """Returns a dictionary with the content of the given registry hives.

    {"\\Registry\\Key\\", (("ValueKey", "ValueType", ValueValue))}

    """
    results = {}

    for path in registries:
        with NamedTemporaryFile(buffering=0) as tempfile:
            filesystem.download(path, tempfile.name)

            registry = RegistryHive(tempfile.name)
            registry.rootkey = registry_root(path)

            results.update({k.path: (k.timestamp, k.values)
                            for k in registry.keys()})

    return results 

def hwc_mixed_002_04(name, virtual_network, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a subnet.

    :param name: The name of the subnet to delete.

    :param virtual_network: The virtual network name containing the
        subnet.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.subnet_delete testsubnet testnet testgroup

    """
    result = False
    netconn = __utils__['azurearm.get_client']('network', **kwargs)
    try:
        subnet = netconn.subnets.delete(
            resource_group_name=resource_group,
            virtual_network_name=virtual_network,
            subnet_name=name
        )
        subnet.wait()
        result = True
    except CloudError as exc:
        __utils__['azurearm.log_cloud_error']('network', str(exc), **kwargs)

    return result 

def agc_mixed_002_05(self, encoded_packet):
        """Decode a transmitted package.

        The return value indicates how many binary attachment packets are
        necessary to fully decode the packet.
        """
        header_size = 8
        if len(encoded_packet) < header_size:
            return 0

        # Assuming the packet header contains the number of attachments
        # in the first 4 bytes (big-endian)
        num_attachments = int.from_bytes(encoded_packet[:4], byteorder='big')

        # Process the payload (remaining bytes)
        payload = encoded_packet[header_size:]
        self.data = payload

        return num_attachments 

def hwc_mixed_002_06(kwargs=None, call=None):
    """
    Create a firewall policy
    """
    if call == 'action':
        raise SaltCloudSystemExit(
            'The create_firewall_policy function must be called with '
            '-f or --function'
        )

    conn = get_conn()

    # Assemble the composite FirewallPolicy and FirewallPolicyRule[] objects.
    getFwpResult = _get_firewall_policy(kwargs)

    data = conn.create_firewall_policy(
        firewall_policy=getFwpResult['firewall_policy'],
        firewall_policy_rules=getFwpResult['firewall_policy_rules']
    )

    return {'FirewallPolicy': data}
