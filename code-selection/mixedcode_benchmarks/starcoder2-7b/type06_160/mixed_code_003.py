def agc_mixed_003_01(self):
        """message receive routine"""
        while True:
            try:
                msg = self.sock.recv(1024)
                if msg:
                    self.msg_queue.put(msg)
                else:
                    break
            except Exception as e:
                print(e)
                break 

def agc_mixed_003_02(self, username, format=None):
        """
        Retrieve the activity stats about a specific user over the last year.

        Params:
            username (string): filters the username of the user whose activity you are interested in.
            format (string): Allows changing the of the date/time returned from iso format
                             to unix timestamp Can be: timestamp or isoformat
        Returns:
            dict: A dictionary of activities done by a given user for all the projects
                  for a given Pagure instance.
        """
        url = self.url + "/api/user/activity/stats"
        params = {"username": username}
        response = self._get(url, params=params)
        if format == "timestamp":
            for project in response:
                for activity in project["activities"]:
                    activity["date"] = datetime.datetime.fromtimestamp(
                        activity["date"]
                    ).isoformat()
        return response 

def hwc_mixed_003_03(self, obj):
        """
        A list_display column containing a checkbox widget.
        """
        if self.check_concurrent_action:
            return helpers.checkbox.render(helpers.ACTION_CHECKBOX_NAME,
                                           force_text("%s,%s" % (obj.pk,
                                                                 get_revision_of_object(obj))))
        else:  # pragma: no cover
            return super(ConcurrencyActionMixin, self).action_checkbox(obj) 

def hwc_mixed_003_04(numbers, indicator='..', base=0):
    """ Merge adjacent numbers in an iterable of numbers.

        Parameters:
            numbers (list): List of integers or numeric strings.
            indicator (str): Delimiter to indicate generated ranges.
            base (int): Passed to the `int()` conversion when comparing numbers.

        Return:
            list of str: Condensed sequence with either ranges or isolated numbers.
    """
    integers = list(sorted([(int("%s" % i, base), i) for i in numbers]))
    idx = 0
    result = []
    while idx < len(numbers):
        end = idx + 1
        while end < len(numbers) and integers[end-1][0] == integers[end][0] - 1:
            end += 1

        result.append("%s%s%s" % (integers[idx][1], indicator, integers[end-1][1])
                      if end > idx + 1
                      else "%s" % integers[idx][1])
        idx = end
    return result 

def hwc_mixed_003_05(self):
        """
        Restores the stored session.

        :return: Method success.
        :rtype: bool
        """

        session = [foundations.strings.to_string(path)
                   for path in self.__settings.get_key(self.__settings_section, "session").toStringList()
                   if foundations.common.path_exists(path)]

        LOGGER.debug("> Restoring session :'{0}'.".format(session))
        success = True
        for path in session:
            if os.path.isfile(path):
                success *= self.load_file(path)
            else:
                success *= self.add_project(path)
        return success 

def agc_mixed_003_06(related_articles):
    """
    Given parsed data build a list of related article objects
    """
    related_articles_list = []
    for article in related_articles:
        related_articles_list.append(
            RelatedArticle(
                title=article.get('title'),
                url=article.get('url'),
                date=article.get('date'),
                author=article.get('author'),
                image=article.get('image'),
                description=article.get('description')
            )
        )
    return related_articles_list
