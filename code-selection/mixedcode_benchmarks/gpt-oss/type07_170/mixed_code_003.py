def hwc_mixed_003_01(self, *args, **kwargs):
        """
        The method to save all translations.
        This can be overwritten to implement any custom additions.
        This method calls :func:`save_translation` for every fetched language.

        :param args: Any custom arguments to pass to :func:`save`.
        :param kwargs: Any custom arguments to pass to :func:`save`.
        """
        # Copy cache, new objects (e.g. fallbacks) might be fetched if users override save_translation()
        # Not looping over the cache, but using _parler_meta so the translations are processed in the order of inheritance.
        local_caches = self._translations_cache.copy()
        for meta in self._parler_meta:
            local_cache = local_caches[meta.model]
            translations = list(local_cache.values())

            # Save all translated objects which were fetched.
            # This also supports switching languages several times, and save everything in the end.
            for translation in translations:
                if is_missing(translation):  # Skip fallback markers
                    continue

                self.save_translation(translation, *args, **kwargs) 

def agc_mixed_003_02(self, args):
    """Handles an event update for this object, e.g. dimmer level change."""
    if not isinstance(args, dict):
        raise TypeError("args must be a dict")
    changed = False
    for key, value in args.items():
        if not hasattr(self, key):
            continue
        current = getattr(self, key)
        if current != value:
            setattr(self, key, value)
            changed = True
    if changed and hasattr(self, "_on_update"):
        try:
            self._on_update(args)
        except Exception:
            pass
    return changed 

def hwc_mixed_003_03(image , col , row):
    """Basic checks for columns and rows values"""
    SPLIT_LIMIT = 99

    try:
        col = int(col)
        row = int(row)
    except:
        raise ValueError('columns and rows values could not be cast to integer.')

    if col < 2:
        raise ValueError('Number of columns must be between 2 and {} (you \
                          asked for {}).'.format(SPLIT_LIMIT, col))
    if row < 2 :
        raise ValueError('Number of rows must be between 2 and {} (you \
                          asked for {}).'.format(SPLIT_LIMIT, row)) 

def hwc_mixed_003_04(remote, resp):
    """Extract token from response and set it for the user.

    :param remote: The remote application.
    :param resp: The response.
    :raises invenio_oauthclient.errors.OAuthClientError: If authorization with
        remote service failed.
    :raises invenio_oauthclient.errors.OAuthResponseError: In case of bad
        authorized request.
    :returns: The token.
    """
    if resp is None:
        raise OAuthRejectedRequestError('User rejected request.', remote, resp)
    else:
        if 'access_token' in resp:
            return oauth2_token_setter(remote, resp)
        elif 'oauth_token' in resp and 'oauth_token_secret' in resp:
            return oauth1_token_setter(remote, resp)
        elif 'error' in resp:
            # Only OAuth2 specifies how to send error messages
            raise OAuthClientError(
                'Authorization with remote service failed.', remote, resp,
            )
    raise OAuthResponseError('Bad OAuth authorized request', remote, resp) 

def agc_mixed_003_05(cls, elem, end_elem, delete_end=True):
        """delete everything from elem to end_elem, including elem.
        if delete_end==True, also including end_elem; otherwise, leave it."""
        try:
            start = cls.index(elem)
        except ValueError:
            raise ValueError(f"{elem!r} not found in collection")
        try:
            end = cls.index(end_elem)
        except ValueError:
            raise ValueError(f"{end_elem!r} not found in collection")
        if start > end:
            raise ValueError("elem occurs after end_elem")
        if delete_end:
            del cls[start:end + 1]
        else:
            del cls[start:end] 

def agc_mixed_003_06(li):
    """Return two lists
        - the last N items of li whose total size is less than MAX_SIZE
        - the rest of the original list li
    """
    # sys.getsizeof is nearly useless. All our data is stringable so rather
    # use that as a measure of size.
    selected = []
    total = 0
    # iterate from the end towards the start
    for item in reversed(li):
        try:
            size = len(item)
        except Exception:
            # fallback to 1 if item has no length
            size = 1
        if total + size > MAX_SIZE:
            break
        selected.append(item)
        total += size
    # selected currently in reverse order; restore original order
    selected.reverse()
    rest = li[:len(li) - len(selected)]
    return selected, rest
