def hwc_mixed_003_01(self):
        """ find all template variables in self._code, excluding the
        function name. 
        """
        template_vars = set()
        for var in parsing.find_template_variables(self._code):
            var = var.lstrip('$')
            if var == self.name:
                continue
            if var in ('pre', 'post'):
                raise ValueError('GLSL uses reserved template variable $%s' % 
                                 var)
            template_vars.add(var)
        return template_vars 

def hwc_mixed_003_02(self):
        """Alter the installation path."""
        install.finalize_options(self)
        if self.prefix is None:
            # no place for man page (like in a 'snap')
            man_dir = None
        else:
            man_dir = os.path.join(self.prefix, "share", "man", "man1")

            # if we have 'root', put the building path also under it (used normally
            # by pbuilder)
            if self.root is not None:
                man_dir = os.path.join(self.root, man_dir[1:])
        self._custom_man_dir = man_dir 

def agc_mixed_003_03(self, hashtag: str,
                         max_count: Optional[int] = None,
                         post_filter: Optional[Callable[[Post], bool]] = None,
                         fast_update: bool = False) -> None:
        """Download pictures of one hashtag.

        To download the last 30 pictures with hashtag #cat, do::

            loader = Instaloader()
            loader.download_hashtag('cat', max_count=30)

        :param hashtag: Hashtag to download, without leading '#'
        :param max_count: Maximum count of pictures to download
        :param post_filter: function(post), which returns True if given picture should be downloaded
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        """
        posts = instaloader.Post.from_hashtag(self.context, hashtag)
        count = 0
        for post in posts:
            if max_count is not None and count >= max_count:
                break
            if post_filter is not None and not post_filter(post):
                continue
            if fast_update and self.is_already_downloaded(post):
                break
            self.download_post(post, target=f'#{hashtag}')
            count += 1 

def hwc_mixed_003_04(parameters, index, left=True, required=False,
                                                  notfoundmsg=None):
    """
    Generate neighbour matching call for HTMLElement, which returns only
    elements with required neighbours.

    Args:
        parameters (list): List of parameters for ``.match()``.
        index (int): Index of the item you want to get from ``.match()`` call.
        left (bool, default True): Look for neigbour in the left side of el.
        required (bool, default False): Use :func:`_required_idiom` to returned
                 data.
        notfoundmsg (str, default None): Message which will be used for
                    :func:`_required_idiom` if the item is not found.

    Returns:
        str: Python code.
    """
    fn_string = "has_neigh(%s, left=%s)" % (
        repr(parameters.fn_params)[1:-1],
        repr(left)
    )

    output = IND + "el = dom.find(\n"
    output += IND + IND + "%s,\n" % repr(parameters.tag_name)

    if parameters.params:
        output += IND + IND + "%s,\n" % repr(parameters.params)

    output += IND + IND + "fn=%s\n" % fn_string
    output += IND + ")\n\n"

    if required:
        return output + _required_idiom(
            parameters.fn_params[0],
            index,
            notfoundmsg
        )

    return output + _index_idiom("el", index) 

def agc_mixed_003_05(self, queue_target, url, json=False, key=None):
        """Request the url service and put the result in the queue_target."""
        import requests

        try:
            params = {'key': key} if key else {}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            if json:
                result = response.json()
            else:
                result = response.text.strip()

            queue_target.put(result)
        except Exception as e:
            queue_target.put(e) 

def agc_mixed_003_06(self, upload_stream, scope_identifier, hub_name, plan_id, timeline_id, record_id, type, name, **kwargs):
        """CreateAttachment.
        [Preview API]
        :param object upload_stream: Stream to upload
        :param str scope_identifier: The project GUID to scope the request
        :param str hub_name: The name of the server hub: "build" for the Build server or "rm" for the Release Management server
        :param str plan_id:
        :param str timeline_id:
        :param str record_id:
        :param str type:
        :param str name:
        :rtype: :class:`<TaskAttachment> <azure.devops.v5_0.task.models.TaskAttachment>`
        """
        url = f"https://{self._base_url}/{hub_name}/{plan_id}/{timeline_id}/{record_id}/attachments"
        params = {
            "scopeIdentifier": scope_identifier,
            "type": type,
            "name": name
        }
        params.update(kwargs)

        response = self._send_request(
            method="POST",
            url=url,
            params=params,
            data=upload_stream
        )

        from azure.devops.v5_0.task.models import TaskAttachment
        return TaskAttachment.from_json(response)
