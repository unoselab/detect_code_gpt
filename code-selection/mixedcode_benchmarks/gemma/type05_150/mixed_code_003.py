def agc_mixed_003_01(first: Histogram1D, second: Histogram2D, *, orientation: str = "vertical", kind: str = "bar", **kwargs):
    """Draw two different histograms mirrored in one figure.

    Parameters
    ----------
    first: Histogram1D
    second: Histogram1D
    color1:
    color2:
    orientation: str

    Returns
    -------
    plt.Axes
    """
    # TODO: enable vertical as well as horizontal
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots()

    x = np.arange(len(first.bins))
    y1 = first.values
    y2 = second.values if hasattr(second, 'values') else second

    if orientation == "vertical":
        ax.bar(x - 0.2, y1, width=0.4, label="First", **kwargs)
        ax.bar(x + 0.2, y2, width=0.4, label="Second", **kwargs)
        ax.set_ylabel("Value")
    else:
        ax.barh(x - 0.2, y1, height=0.4, label="First", **kwargs)
        ax.barh(x + 0.2, y2, height=0.4, label="Second", **kwargs)
        ax.set_xlabel("Value")

    ax.set_xticks(x)
    ax.set_xticklabels(first.bins)
    ax.legend()

    return ax 

def hwc_mixed_003_02(self, viewNo: int):
        """
        Notifies primary decider about the fact that view changed to let it
        prepare for election, which then will be started from outside by
        calling decidePrimaries()
        """
        if viewNo <= self.viewNo:
            logger.warning("{}Provided view no {} is not greater"
                           " than the current view no {}"
                           .format(VIEW_CHANGE_PREFIX, viewNo, self.viewNo))
            return False
        self.previous_master_primary = self.node.master_primary_name
        for replica in self.replicas.values():
            replica.primaryName = None
        return True 

def agc_mixed_003_03(env, identifier, postinstall, key, image):
    """Reload operating system on a virtual server."""

    import subprocess
    cmd = [
        "virt-install",
        "--name", identifier,
        "--os-variant", env,
        "--location", image,
        "--extra-args", f"console=ttyS0,115200n8 earlyprintk=ttyS0,115200",
        "--disk", f"size=10,target=vda",
        "--network", "bridge=br0",
        "--graphics", "none",
        "--boot", "hd,network"
    ]
    if postinstall and key:
        cmd.append(f"--extra-args=cloud-init-key={key}")

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError:
        return False 

def hwc_mixed_003_04(self):
        """ to_dict: puts channel data into the format that Kolibri Studio expects
            Args: None
            Returns: dict of channel data
        """
        return {
            "id": self.get_node_id().hex,
            "name": self.title,
            "thumbnail": self.thumbnail.filename if self.thumbnail else None,
            "language" : self.language,
            "description": self.description or "",
            "license": self.license,
            "source_domain": self.source_domain,
            "source_id": self.source_id,
            "ricecooker_version": __version__,
        } 

def hwc_mixed_003_05(self, value, redis, *, commit=True):
        """ Sets this fields value in the databse """
        value = self.prepare(value)

        if value is not None:
            redis.hset(self.obj.key(), self.name, value)
        else:
            redis.hdel(self.obj.key(), self.name)

        if self.index:
            key = self.key()

            if self.name in self.obj._old:
                redis.hdel(key, self.obj._old[self.name])

            if value is not None:
                redis.hset(key, value, self.obj.id) 

def agc_mixed_003_06(profile=None, **kwargs):
    """
    Set up nova credentials
    """
    if profile:
        import keystoneauth1.identity
        import novaclient
        auth_plugin = keystoneauth1.identity.plugins.OpenStackIdentityPlugin(
            auth_url=kwargs.get('auth_url'),
            username=kwargs.get('username'),
            password=kwargs.get('password'),
            project_name=kwargs.get('project_name'),
            user_domain_name=kwargs.get('user_domain_name'),
            project_domain_name=kwargs.get('project_domain_name'),
        )
        return novaclient.Client(version='2.0', auth=auth_plugin)

    import novaclient
    from novaclient.v2.client import Client
    return Client(version='2.0', **kwargs)
