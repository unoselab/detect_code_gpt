def hwc_mixed_001_01(self, subscription):
        """
        Allows endpoint owner to delete subscription.
        Confirmation message will be delivered.

        :type subscription: string
        :param subscription: The ARN of the subscription to be deleted.

        """
        params = {'ContentType' : 'JSON',
                  'SubscriptionArn' : subscription}
        response = self.make_request('Unsubscribe', params, '/', 'GET')
        body = response.read()
        if response.status == 200:
            return json.loads(body)
        else:
            boto.log.error('%s %s' % (response.status, response.reason))
            boto.log.error('%s' % body)
            raise self.ResponseError(response.status, response.reason, body) 

def agc_mixed_001_02(self, sortkey = False):
        """
        Return `(key, value)` tuples for all mapped configurations for this object
        """
        if hasattr(self, "_config_map") and isinstance(self._config_map, dict):
            items = list(self._config_map.items())
        else:
            # Fallback: use public attributes (exclude private and callables)
            items = [(k, v) for k, v in vars(self).items()
                     if not k.startswith("_") and not callable(v)]
        if sortkey:
            items.sort(key=lambda kv: kv[0])
        return items 

def agc_mixed_001_03(y, y_pred):
    """F1 score

    f1_score = 2 * precision*recall / (precision + recall)

    Parameters:
    -----------
    y : vector, shape (n_samples,)
    The target labels.

    y_pred : vector, shape (n_samples,)
    The predicted labels.

    Returns:
    --------
    f1_score : float

    """

    import numpy as np
    y = np.asarray(y)
    y_pred = np.asarray(y_pred)

    tp = np.sum((y == 1) & (y_pred == 1))
    fp = np.sum((y == 0) & (y_pred == 1))
    fn = np.sum((y == 1) & (y_pred == 0))

    if tp + fp == 0 or tp + fn == 0:
        return 0.0

    precision = tp / (tp + fp)
    recall = tp / (tp + fn)

    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall) 

def agc_mixed_001_04(self, auth_secret):
        """Get the profile (i.e., username, password, etc.) of a user.

        Parameters
        ----------
        auth_secret: str
            The authentication secret of the logged-in user.

        Returns
        -------
        bool
            True if the logout is successful, False otherwise.
        result
            A dict containing the following keys:

            -  USERNAME_KEY
            -  PASSWORD_HASH_KEY
            -  AUTH_KEY

            if the user profile is obtained successfully; otherwise a dict
            containing the error string with the key ERROR_KEY.

        Note
        ----
        Possible error strings are listed as below:

        -  ERROR_NOT_LOGGED_IN
        """
        if not hasattr(self, "_auth_sessions") or auth_secret not in self._auth_sessions:
            return False, {ERROR_KEY: ERROR_NOT_LOGGED_IN}

        # Retrieve stored profile information
        stored = self._auth_sessions[auth_secret]

        # Build the result dictionary using the expected keys
        result = {
            USERNAME_KEY: stored.get("username"),
            PASSWORD_HASH_KEY: stored.get("password_hash"),
            AUTH_KEY: stored.get("auth_key"),
        }

        return True, result 

def hwc_mixed_001_05(path):
    """
    | Creates a directory with given path.
    | The directory creation is delegated to
        Python :func:`os.makedirs` definition so that directories hierarchy is recursively created.

    :param path: Directory path.
    :type path: unicode
    :return: Definition success.
    :rtype: bool
    """

    try:
        if not foundations.common.path_exists(path):
            LOGGER.debug("> Creating directory: '{0}'.".format(path))
            os.makedirs(path)
            return True
        else:
            LOGGER.debug("> '{0}' directory already exist, skipping creation!".format(path))
            return True
    except Exception as error:
        raise foundations.exceptions.DirectoryCreationError(
            "!> {0} | Cannot create '{1}' directory: '{2}'".format(__name__, path, error)) 

def hwc_mixed_001_06(self, friendly_name=values.unset):
        """
        Update the SigningKeyInstance

        :param unicode friendly_name: The friendly_name

        :returns: Updated SigningKeyInstance
        :rtype: twilio.rest.api.v2010.account.signing_key.SigningKeyInstance
        """
        data = values.of({'FriendlyName': friendly_name, })

        payload = self._version.update(
            'POST',
            self._uri,
            data=data,
        )

        return SigningKeyInstance(
            self._version,
            payload,
            account_sid=self._solution['account_sid'],
            sid=self._solution['sid'],
        )
