def hwc_mixed_005_01(self, src, snk, new_layer, new_keras_layer):
        """
        Insert the new_layer before layer, whose position is layer_idx. The new layer's
        parameter is stored in a Keras layer called new_keras_layer
        """
        if snk is None:
            insert_pos = self.layer_list.index(src) + 1
        else:
            insert_pos = self.layer_list.index(snk) # insert position
        self.layer_list.insert(insert_pos, new_layer)
        self.keras_layer_map[new_layer] = new_keras_layer
        if src is None: # snk is an input layer
            self._add_edge(new_layer, snk)
        elif snk is None:  # src is an output layer
            self._add_edge(src, new_layer)
        else:
            self._add_edge(src, new_layer)
            self._add_edge(new_layer, snk)
            self._remove_edge(src, snk) 

def hwc_mixed_005_02(self, signum):
        """Invoked whenever a signal is added to the stack.

        :param int signum: The signal that was added

        """
        if signum == signal.SIGTERM:
            LOGGER.info('Received SIGTERM, initiating shutdown')
            self.stop()
        elif signum == signal.SIGHUP:
            LOGGER.info('Received SIGHUP')
            if self.config.reload():
                LOGGER.info('Configuration reloaded')
                logging.config.dictConfig(self.config.logging)
                self.on_configuration_reloaded()
        elif signum == signal.SIGUSR1:
            self.on_sigusr1()
        elif signum == signal.SIGUSR2:
            self.on_sigusr2() 

async def hwc_mixed_005_03(
        url: typing.Union[str, ParseResult, SplitResult],
        insecure: bool = False):
    """Fetch the API description from the remote MAAS instance."""
    url_describe = urljoin(_ensure_url_string(url), "describe/")
    connector = aiohttp.TCPConnector(verify_ssl=(not insecure))
    session = aiohttp.ClientSession(connector=connector)
    async with session, session.get(url_describe) as response:
        if response.status != HTTPStatus.OK:
            raise RemoteError(
                "{0} -> {1.status} {1.reason}".format(
                    url, response))
        elif response.content_type != "application/json":
            raise RemoteError(
                "Expected application/json, got: %s"
                % response.content_type)
        else:
            return await response.json() 

def agc_mixed_005_04():
    """Preprocesses the fallback include and library paths depending on the
    platform."""
    import sys
    if sys.platform == 'win32':
        return {
            'include': ['C:\\Program Files (x86)\\Windows Kits\\10\\Include', 'C:\\Program Files (x86)\\Microsoft Visual Studio'],
            'lib': ['C:\\Program Files (x86)\\Windows Kits\\10\\Lib', 'C:\\Program Files (x86)\\Microsoft Visual Studio']
        }
    elif sys.platform == 'darwin':
        return {
            'include': ['/usr/local/include', '/usr/include'],
            'lib': ['/usr/local/lib', '/usr/lib']
        }
    else:
        return {
            'include': ['/usr/include', '/usr/local/include'],
            'lib': ['/usr/lib', '/usr/local/lib']
        } 

def agc_mixed_005_05(self, node):
        """
        >>> import gast as ast
        >>> from pythran import passmanager, backend
        >>> pm = passmanager.PassManager("test")

        >>> node = ast.parse("def foo(a): a[1:][3]")
        >>> _, node = pm.apply(PartialConstantFolding, node)
        >>> _, node = pm.apply(ConstantFolding, node)
        >>> print(pm.dump(backend.Python, node))
        def foo(a):
            a[4]

        >>> node = ast.parse("def foo(a): a[::2][3]")
        >>> _, node = pm.apply(PartialConstantFolding, node)
        >>> _, node = pm.apply(ConstantFolding, node)
        >>> print(pm.dump(backend.Python, node))
        def foo(a):
            a[6]

        >>> node = ast.parse("def foo(a): a[-4:][5]")
        >>> _, node = pm.apply(PartialConstantFolding, node)
        >>> _, node = pm.apply(ConstantFolding, node)
        >>> print(pm.dump(backend.Python, node))
        def foo(a):
            a[1]
        """
        val = node.value.value
        s1 = node.value.slice
        s2 = node.slice
        if (isinstance(s1.lower, gast.Num) and isinstance(s1.upper, gast.Num) and
            isinstance(s2, gast.Num)):
            return gast.Subscript(value=val, slice=gast.Num(n=s1.lower.n + s2.n), ctx=node.ctx)
        if (isinstance(s1.lower, gast.Num) and isinstance(s1.upper, gast.Num) and
            isinstance(s2, gast.Num)):
            return gast.Subscript(value=val, slice=gast.Num(n=s1.lower.n + s2.n), ctx=node.ctx)
        if (isinstance(s1.lower, gast.Num) and isinstance(s1.upper, gast.Num) and
            isinstance(s1.step, gast.Num) and isinstance(s2, gast.Num)):
            return gast.Subscript(value=val, slice=gast.Num(n=s1.lower.n + s2.n * s1.step.n), ctx=node.ctx)
        return node 

def agc_mixed_005_06(self, name=None, count=10, delete=False):
        """
        Show up to ``count`` messages from the queue named ``name``. If ``name``
        is None, show for each queue in our config. If ``delete`` is True,
        delete the messages after showing them.

        :param name: queue name, or None for all queues in config.
        :type name: str
        :param count: maximum number of messages to get from queue
        :type count: int
        :param delete: whether or not to delete messages after receipt
        :type delete: bool
        """
        queues = [name] if name else self.config.get('queues', [])
        for q_name in queues:
            messages = self.get_messages(q_name, count=count)
            if not messages:
                print(f"Queue {q_name}: Empty")
                continue

            print(f"Queue {q_name}:")
            for msg in messages:
                print(msg)
                if delete:
                    self.delete_message(q_name, msg.id)
