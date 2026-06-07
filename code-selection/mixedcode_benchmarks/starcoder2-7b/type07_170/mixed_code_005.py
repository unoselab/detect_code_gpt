def agc_mixed_005_01(self, *args, **kwargs): #pylint: disable=invalid-name
        """
        Determining whether args/kwargs are the ONLY matched args/kwargs called previously
        Handle each arg/kwarg as a SinonMatcher
        Return: Boolean
        """
        if self.match_args is None:
            return False
        if len(self.match_args)!= len(args):
            return False
        if len(self.match_kwargs)!= len(kwargs):
            return False
        for i, arg in enumerate(args):
            if not self.match_args[i].matches(arg):
                return False
        for key, value in kwargs.items():
            if not self.match_kwargs[key].matches(value):
                return False
        return True 

def agc_mixed_005_02(self, remove=True, insert=True, volume=None):
        """
        Give max capacity in mAh/cc for inserting and removing a charged cation into base structure.

        Args:
            remove: (bool) whether to allow cation removal
            insert: (bool) whether to allow cation insertion
            volume: (float) volume to use for normalization (default=volume of initial structure)

        Returns:
            max vol capacity in mAh/cc
        """

        if volume is None:
            volume = self.get_volume()
        if remove:
            if insert:
                return self.get_max_capvol_insert_remove(volume)
            else:
                return self.get_max_capvol_remove(volume)
        else:
            if insert:
                return self.get_max_capvol_insert(volume)
            else:
                return 0 

def hwc_mixed_005_03(self):
        """ Function load
        Get the list of all objects

        @return RETURN: A ForemanItem list
        """
        cl_tmp = self.api.list(self.objName, limit=self.searchLimit).values()
        cl = []
        for i in cl_tmp:
            cl.extend(i)
        return {x[self.index]: ItemPuppetClass(self.api, x['id'],
                                               self.objName, self.payloadObj,
                                               x)
                for x in cl} 

def hwc_mixed_005_04(self):
        """
            யாரிகழ்ந்து =
                [['ய்', 'ஆரிகழ்ந்து'],
                 ['யார்', 'இகழ்ந்து'],
                 ['யாரிக்', 'அழ்ந்து'],
                 ['யாரிகழ்ந்த்', 'உ']]
        """
        L = len(self.letters)-1
        for idx,letter in enumerate(self.letters):
            if not( letter in tamil.utf8.grantha_uyirmei_letters):
                continue
            muthal = idx == 0 and u"" or u"".join(self.letters[0:idx])
            meethi = idx == L and u"" or u"".join(self.letters[idx+1:])
            mei,uyir = tamil.utf8.splitMeiUyir(letter)
            muthal = muthal + mei
            meethi = uyir + meethi
            self.results.append([muthal,meethi])
        return len(self.results) > 0 

def hwc_mixed_005_05(keyword, feature, parent):
    """Given a keyword, it will return the value of the keyword
    from the hazard layer's extra keywords.

    For instance:
    *   hazard_extra_keyword( 'depth' ) -> will return the value of 'depth'
        in current hazard layer's extra keywords.
    """
    _ = feature, parent  # NOQA
    hazard_layer_path = QgsExpressionContextUtils. \
        projectScope(QgsProject.instance()).variable(
          'hazard_layer')
    hazard_layer = load_layer(hazard_layer_path)[0]
    keywords = KeywordIO.read_keywords(hazard_layer)
    extra_keywords = keywords.get('extra_keywords')
    if extra_keywords:
        value = extra_keywords.get(keyword)
        if value:
            value_definition = definition(value)
            if value_definition:
                return value_definition['name']
            return value
        else:
            return tr('Keyword %s is not found' % keyword)
    return tr('No extra keywords found') 

def agc_mixed_005_06(
    debug=False,
    host=None,
    key=None,
    proxy=None,
    user_agent=None,
    headers=None,
    rate_limit=True,
    rate_limit_callback=None,
    error_retry_max=None,
    error_retry_backoff=None,
    error_retry_codes=None,
):
    """Initialise the API."""
    global _api
    if _api is None:
        _api = API(
            debug=debug,
            host=host,
            key=key,
            proxy=proxy,
            user_agent=user_agent,
            headers=headers,
            rate_limit=rate_limit,
            rate_limit_callback=rate_limit_callback,
            error_retry_max=error_retry_max,
            error_retry_backoff=error_retry_backoff,
            error_retry_codes=error_retry_codes,
        )
    return _api
