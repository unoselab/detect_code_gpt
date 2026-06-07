def hwc_mixed_004_01(self, response):
        """
        Handle a response from the broker.
        """
        correlation_id = response[0:4]
        try:
            d = self._pending.pop(correlation_id)
        except KeyError:
            self._log.warn((
                "Response has unknown correlation ID {correlation_id!r}."
                " Dropping connection to {peer}."
            ), correlation_id=correlation_id, peer=self.transport.getPeer())
            self.transport.loseConnection()
        else:
            d.callback(response) 

def agc_mixed_004_02(self, request, response, forum):
        """ Sends the signal associated with the view. """
        if not hasattr(self, 'signal'):
            return

        if self.signal == 'post_save':
            signals.post_save.send(sender=self, instance=response,
                                   request=request, forum=forum)
        elif self.signal == 'post_delete':
            signals.post_delete.send(sender=self, instance=response,
                                     request=request, forum=forum) 

def hwc_mixed_004_03(self):
        """
        :rtype : an iterator to the temporary directories containing jobs/stats files
        in the hierarchy of directories in self.tempFilesDir
        """
        def _dirs(path, levels):
            if levels > 0:
                for subPath in os.listdir(path):
                    for i in _dirs(os.path.join(path, subPath), levels-1):
                        yield i
            else:
                yield path
        for tempDir in _dirs(self.tempFilesDir, self.levels):
            yield tempDir 

def hwc_mixed_004_04(self, goid):
        """Get GO text from GOEA study."""
        if self.go2res is not None:
            res = self.go2res.get(goid, None)
            if res is not None:
                if self.study_items is not None:
                    return self._get_item_str(res)
                else:
                    return self.pltvars.fmtres.format(
                        study_count=res.study_count) 

def agc_mixed_004_05(self, uri, http_method='GET', body=None,
                              headers=None, credentials=None):
        """Extract grant_type and route to the designated handler."""
        if not headers:
            headers = {}

        if credentials:
            headers['Authorization'] = 'Basic ' + credentials

        grant_type = self.get_grant_type(headers)
        if grant_type:
            return self.token_response(uri, http_method, body, headers,
                                       grant_type)
        else:
            return self.invalid_request(uri, http_method, body, headers) 

def agc_mixed_004_06(self, dc, node, x, y, w, h, depth):
        """ Draw the icon, if any, and the label, if any, of the node. """
        if self.HasAGWFlag(FNB_NO_X_BUTTON):
            return

        if node.HasChildren():
            if node.IsOpened():
                self.DrawButton(dc, x, y, w, h, wx.AUI_BUTTON_STATE_NORMAL)
            else:
                self.DrawButton(dc, x, y, w, h, wx.AUI_BUTTON_STATE_HIDDEN)

        if node.HasImage():
            self.DrawIcon(dc, node, x, y, w, h)

        if node.HasText():
            self.DrawText(dc, node, x, y, w, h)
