def agc_mixed_003_01(self, goal):
        """Get the shortest way between two nodes of the graph

        Args:
            goal (str): Name of the targeted node
        Return:
            list of Node
        """
        if goal not in self.nodes:
            raise ValueError("Node {} not in graph".format(goal))

        if self.nodes[goal].parent is None:
            raise ValueError("Node {} has no parent".format(goal))

        path = []
        node = self.nodes[goal]
        while node.parent is not None:
            path.append(node)
            node = node.parent
        path.append(node)
        path.reverse()
        return path 

def hwc_mixed_003_02(self, line_str):
        """Split line and check number of columns"""
        arr = line_str.rstrip().split("\t")
        if len(arr) != self.expected_fields:
            raise exceptions.InvalidRecordException(
                (
                    "The line contains an invalid number of fields. Was "
                    "{} but expected {}\n{}".format(len(arr), 9 + len(self.samples.names), line_str)
                )
            )
        return arr 

def agc_mixed_003_03(mode, num_layers, input_size, hidden_size, dropout, weight_dropout):
    """create rnn layer given specs"""
    if mode == 'LSTM':
        return nn.LSTM(input_size, hidden_size, num_layers, dropout=dropout,
                       bidirectional=True, batch_first=True)
    elif mode == 'GRU':
        return nn.GRU(input_size, hidden_size, num_layers, dropout=dropout,
                      bidirectional=True, batch_first=True)
    elif mode == 'RNN':
        return nn.RNN(input_size, hidden_size, num_layers, dropout=dropout,
                      bidirectional=True, batch_first=True)
    else:
        raise ValueError('Unknown mode: %s' % mode) 

def hwc_mixed_003_04(self, owner, access):
        """Fire when the lock *might* be available. The caller will need to
        check with isAvailable() when the deferred fires. This loose form is
        used to avoid deadlocks. If we were interested in a stronger form,
        this would be named 'waitUntilAvailable', and the deferred would fire
        after the lock had been claimed.
        """
        debuglog("%s waitUntilAvailable(%s)" % (self, owner))
        assert isinstance(access, LockAccess)
        if self.isAvailable(owner, access):
            return defer.succeed(self)
        d = defer.Deferred()

        # Are we already in the wait queue?
        w = [i for i, w in enumerate(self.waiting) if w[0] is owner]
        if w:
            self.waiting[w[0]] = (owner, access, d)
        else:
            self.waiting.append((owner, access, d))
        return d 

def hwc_mixed_003_05(self):
        """Closes the VISA session and marks the handle as invalid.
        """
        try:
            logger.debug('%s - closing', self._resource_name,
                         extra=self._logging_extra)
            self.before_close()
            self.visalib.close(self.session)
            logger.debug('%s - is closed', self._resource_name,
                         extra=self._logging_extra)
            self.session = None
        except errors.InvalidSession:
            pass 

def agc_mixed_003_06(self, blueprint, force=False):
        """Pushes the rendered blueprint's template to S3.

        Verifies that the template doesn't already exist in S3 before
        pushing.

        Returns the URL to the template in S3.
        """
        if not force and self.s3_template_exists():
            raise RuntimeError(
                "Template already exists in S3. "
                "Use --force to overwrite."
            )

        template_url = self.s3_client.upload_template(
            self.rendered_template,
            self.blueprint.name,
            self.blueprint.version,
        )
        return template_url
