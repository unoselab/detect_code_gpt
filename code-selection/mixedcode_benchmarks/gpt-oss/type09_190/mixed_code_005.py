def agc_mixed_005_01(content):
    """Load a Procfile from a string."""
    result = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            raise ValueError(f"Invalid Procfile line (missing ':'): {raw_line!r}")
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid Procfile line (empty process type): {raw_line!r}")
        if not value:
            raise ValueError(f"Invalid Procfile line (empty command): {raw_line!r}")
        result[key] = value
    return result 

def agc_mixed_005_02(self):
        """Copy or coerce to a Host."""
        try:
            from .host import Host
        except Exception:
            from host import Host
        if isinstance(self, Host):
            # Return a shallow copy to avoid mutating the original
            import copy
            return copy.copy(self)
        if isinstance(self, str):
            return Host(self)
        if hasattr(self, "host"):
            h = getattr(self, "host")
            if isinstance(h, Host):
                return h 

def hwc_mixed_005_03(self, name, columns, points):
        """Write the points in Riemann."""
        for i in range(len(columns)):
            if not isinstance(points[i], Number):
                continue
            else:
                data = {'host': self.hostname, 'service': name + " " + columns[i], 'metric': points[i]}
                logger.debug(data)
                try:
                    self.client.send(data)
                except Exception as e:
                    logger.error("Cannot export stats to Riemann (%s)" % e) 

def hwc_mixed_005_04(self, collection_name):
        """
        Get PyMongo client pointing to the current DB and the given collection.

        :return: MongoDB client of the current database and given collection.
        :raise DataSourceError
        """
        try:
            return self._database[collection_name]
        except InvalidName as ex:
            raise DataSourceError("Cannot access MongoDB collection %s!"
                                  % collection_name) from ex
        except Exception as ex:
            raise DataSourceError("Unexpected error when accessing MongoDB"
                                  "collection %s!"
                                  % collection_name) from ex 

def agc_mixed_005_05(self, client_id, title, unsubscribe_page, confirmed_opt_in,
               confirmation_success_page, unsubscribe_setting="AllClientLists"):
        """Creates a new list for a client."""
        payload = {
            "title": title,
            "unsubscribePage": unsubscribe_page,
            "confirmedOptIn": confirmed_opt_in,
            "confirmationSuccessPage": confirmation_success_page,
            "unsubscribeSetting": unsubscribe_setting,
        }
        url = f"{self.base_url}/clients/{client_id}/lists"
        session = getattr(self, "session", None)
        if session is not None:
            response = session.post(url, json=payload)
        else:
            import requests
            response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json() 

def hwc_mixed_005_06(self, subscription_id, size=None, cursor=None):
        """ Pulls a series of interactions from the queue for the given subscription ID.

            Uses API documented at http://dev.datasift.com/docs/api/rest-api/endpoints/pull

            :param subscription_id: The ID of the subscription to pull interactions for
            :type subscription_id: str
            :param size: the max amount of data to pull in bytes
            :type size: int
            :param cursor: an ID to use as the point in the queue from which to start fetching data
            :type cursor: str
            :returns: dict with extra response data
            :rtype: :class:`~datasift.request.ResponseList`
            :raises: :class:`~datasift.exceptions.DataSiftApiException`, :class:`requests.exceptions.HTTPError`
        """
        params = {'id': subscription_id}
        if size:
            params['size'] = size
        if cursor:
            params['cursor'] = cursor
        raw = self.request('get', 'pull', params=params)

        def pull_parser(headers, data):
            pull_type = headers.get("X-DataSift-Format")
            if pull_type in ("json_meta", "json_array"):
                return json.loads(data)
            else:
                lines = data.strip().split("\n").__iter__()
                return list(map(json.loads, lines))

        return self.request.build_response(raw, parser=pull_parser)
