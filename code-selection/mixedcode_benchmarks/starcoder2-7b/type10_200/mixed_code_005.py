def agc_mixed_005_01(name, withdecryption=False, resp_json=False, region=None, key=None, keyid=None, profile=None):
    """
    Retrives a parameter from SSM Parameter Store

    .. versionadded:: Neon

    .. code-block:: text

        salt-call boto_ssm.get_parameter test-param withdescription=True
    """
    if not key and not keyid and not profile:
        key, keyid, profile = get_key_id_and_profile()

    if not keyid:
        keyid = key

    if not key:
        key = keyid

    if not region:
        region = get_region()

    conn = _get_conn(region, key, keyid, profile)

    try:
        if withdecryption:
            parameter = conn.get_parameter(name, with_decryption=True)
        else:
            parameter = conn.get_parameter(name)
    except boto.exception.BotoServerError as e:
        if e.error_code == 'ParameterNotFound':
            return None
        raise
    if resp_json:
        return parameter
    else:
        return parameter.value 

def hwc_mixed_005_02(self, frame_in):
        """Handle a Basic Return Frame and treat it as an error.

        :param specification.Basic.Return frame_in: Amqp frame.

        :return:
        """
        reply_text = try_utf8_decode(frame_in.reply_text)
        message = (
            "Message not delivered: %s (%s) to queue '%s' from exchange '%s'" %
            (
                reply_text,
                frame_in.reply_code,
                frame_in.routing_key,
                frame_in.exchange
            )
        )
        exception = AMQPMessageError(message,
                                     reply_code=frame_in.reply_code)
        self.exceptions.append(exception) 

def agc_mixed_005_03(self, query, page=None, per_page=1000, mentions=3, data=False):
        """
        Retrieve all objects that make a search query.

        Will loop through all pages that match unless you provide
        the number of pages you'd like to restrict the search to.

        Example usage:

            >> documentcloud.documents.search('salazar')
        """
        # If the user provides a page, search it and stop there
        if page is None:
            page = 1
        else:
            page = int(page)

        results = []
        while True:
            if page > 1:
                results += self.search(query, page=page-1, per_page=per_page, mentions=mentions, data=data)
            else:
                results += self.search(query, page=page, per_page=per_page, mentions=mentions, data=data)
            if len(results) >= per_page:
                break
            page += 1

        return results 

def hwc_mixed_005_04(self, pattern):
        # type: (str) -> str
        r"""
        Clean up urlpattern regexes into something readable by humans:

        From:
        > "^(?P<sport_slug>\w+)/athletes/(?P<athlete_slug>\w+)/$"

        To:
        > "{sport_slug}/athletes/{athlete_slug}/"
        """
        # remove optional params
        # TODO(dcramer): it'd be nice to change these into [%s] but it currently
        # conflicts with the other rules because we're doing regexp matches
        # rather than parsing tokens
        result = self._optional_group_matcher.sub(lambda m: "%s" % m.group(1), pattern)

        # handle named groups first
        result = self._named_group_matcher.sub(lambda m: "{%s}" % m.group(1), result)

        # handle non-named groups
        result = self._non_named_group_matcher.sub("{var}", result)

        # handle optional params
        result = self._either_option_matcher.sub(lambda m: m.group(1), result)

        # clean up any outstanding regex-y characters.
        result = (
            result.replace("^", "")
            .replace("$", "")
            .replace("?", "")
            .replace("//", "/")
            .replace("\\", "")
        )

        return result 

def hwc_mixed_005_05(self, session):
        """Sets the underlying operable views to match current view"""
        for obj_name in self._operable_views:
            if self._operable_views[obj_name] == ACTIVE:
                try:
                    getattr(session, 'use_active_' + obj_name + '_view')()
                except AttributeError:
                    pass
            else:
                try:
                    getattr(session, 'use_any_status_' + obj_name + '_view')()
                except AttributeError:
                    pass 

def agc_mixed_005_06(self):
        """Convert posterior_predictive samples to xarray."""
        return xr.Dataset(
            {
                "posterior_predictive": (
                    ["sample", "chain", "draw", "obs_dim_0"],
                    self.posterior_predictive,
                )
            },
            coords={
                "chain": np.arange(self.posterior_predictive.shape[1]),
                "draw": np.arange(self.posterior_predictive.shape[2]),
                "obs_dim_0": np.arange(self.posterior_predictive.shape[3]),
            },
        )
