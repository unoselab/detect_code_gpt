def hwc_mixed_003_01(self):
        """
        Assumes postgres now talks to pg_ctl, but might not yet be listening
        or connections from psql.  Test that psql is able to connect, as
        it occasionally takes 5-10 seconds for postgresql to start listening.
        """
        cmd = self._psql_cmd()
        for i in range(50, -1, -1):
            res = subprocess.call(
                cmd, stdin=DEV_NULL, stdout=DEV_NULL,
                stderr=DEV_NULL)
            if res == 0:
                break
            time.sleep(0.2)
        return i != 0 

def hwc_mixed_003_02(self) -> Iterator[PostSidecarNode]:
        """Sidecar nodes of a Post with typename==GraphSidecar."""
        if self.typename == 'GraphSidecar':
            for edge in self._field('edge_sidecar_to_children', 'edges'):
                node = edge['node']
                is_video = node['is_video']
                yield PostSidecarNode(is_video=is_video, display_url=node['display_url'],
                                      video_url=node['video_url'] if is_video else None) 

def agc_mixed_003_03(self, y):
        r"""
        Updates the moments (x_hat, Sigma) of the time t prior to the
        time t filtering distribution, using current measurement :math:`y_t`.

        The updates are according to

        .. math::

            \hat{x}^F = \hat{x} + \Sigma G' (G \Sigma G' + R)^{-1}
                (y - G \hat{x})
            \Sigma^F = \Sigma - \Sigma G' (G \Sigma G' + R)^{-1} G
                \Sigma

        Parameters
        ----------
        y : scalar or array_like(float)
            The current measurement

        """
        # === simplify notation === #
        import numpy as np
        y = np.asarray(y)
        G = self.G
        R = self.R
        Sigma = self.Sigma
        x_hat = self.x_hat

        S = G @ Sigma @ G.T + R
        K = Sigma @ G.T @ np.linalg.inv(S)

        self.x_hat = x_hat + K @ (y - G @ x_hat)
        self.Sigma = Sigma - K @ G @ Sigma 

def agc_mixed_003_04(self, env, fromdocname, builder,
                     typ, target, node, contnode):
        # type: (BuildEnvironment, unicode, Builder, unicode, unicode, nodes.Node, nodes.Node) -> nodes.Node  # NOQA
        """Resolve the pending_xref *node* with the given *typ* and *target*.

        This method should return a new node, to replace the xref node,
        containing the *contnode* which is the markup content of the
        cross-reference.

        If no resolution can be found, None can be returned; the xref node will
        then given to the :event:`missing-reference` event, and if that yields no
        resolution, replaced by *contnode*.

        The method can also raise :exc:`sphinx.environment.NoUri` to suppress
        the :event:`missing-reference` event being emitted.
        """
        try:
            target_node = env.find_xref_target(typ, target)
        except Exception:
            return None

        if target_node is None:
            return None

        # Create a reference node to the target
        refnode = nodes.reference('', contnode)
        refnode['refuri'] = self.get_uri(builder, target_node)
        refnode['refdocname'] = target_node.get('refdocname', fromdocname)

        return refnode 

def agc_mixed_003_05(self, walk_folders=False, walk_files=False):
        """
        A simple generator that yields a File or Folder object based on
        the arguments.
        """

        for root, dirs, files in os.walk(self.path):
            if walk_folders:
                for d in dirs:
                    yield Folder(os.path.join(root, d))
            if walk_files:
                for f in files:
                    yield File(os.path.join(root, f)) 

def hwc_mixed_003_06(self):
        """Send an ON message to device group."""
        on_command = ExtendedSend(self._address,
                                  COMMAND_LIGHT_ON_0X11_NONE,
                                  self._udata,
                                  cmd2=0xff)
        on_command.set_checksum()
        self._send_method(on_command, self._on_message_received)
