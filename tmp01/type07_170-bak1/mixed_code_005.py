def hwc_mixed_005_01(self, value):
        """
        from value to datetime with tzinfo format (datetime.datetime instance)
        """
        if isinstance(value, (six.integer_types, float, six.string_types)):
            value = self.to_naive_datetime(value)

        if isinstance(value, datetime.datetime):
            if timezone.is_naive(value):
                value = timezone.make_aware(value, timezone.utc)
            else:
                value = timezone.localtime(value, timezone.utc)
            return value

        raise exceptions.ValidationError(
            "Unable to convert value: '%s' to python data type" % value,
            code="invalid_datetime"
        ) 

def hwc_mixed_005_02(self):
        """
        Return the object id for this master, for associating state with the
        master.

        @returns: ID, via Deferred
        """
        # try to get the cached value
        if self._object_id is not None:
            return defer.succeed(self._object_id)

        # failing that, get it from the DB; multiple calls to this function
        # at the same time will not hurt

        d = self.db.state.getObjectId(self.name,
                                      "buildbot.master.BuildMaster")

        @d.addCallback
        def keep(id):
            self._object_id = id
            return id
        return d 

def agc_mixed_005_03(self, poll, thread_id=None):
        """
        Creates poll in a group thread

        :param poll: Poll to create
        :param thread_id: User/Group ID to create poll in. See :ref:`intro_threads`
        :type poll: models.Poll
        :raises: FBchatException if request failed
        """
        if not isinstance(poll, models.Poll):
            raise FBchatException("poll must be of type models.Poll")
        if not thread_id:
            thread_id = self._active_thread
        if not thread_id:
            raise FBchatException("Thread ID must be set")
        return self._graphql_request(
            query_name="create_poll",
            variables={
                "thread_id": thread_id,
                "poll": poll.to_json(),
            },
        ) 

def agc_mixed_005_04(self, src, dst):
        """Copy file or directory."""

        if os.path.isdir(src):
            if not os.path.isdir(dst):
                os.makedirs(dst)
            files = os.listdir(src)
            for f in files:
                if os.path.isdir(os.path.join(src, f)):
                    cp(os.path.join(src, f), os.path.join(dst, f))
                else:
                    shutil.copy2(os.path.join(src, f), dst)
        else:
            shutil.copy2(src, dst) 

def agc_mixed_005_05(line, begin_delim=begin_delim,
                     end_delim=end_delim):
    """Split a line into alternating groups.
       The first group cannot have a line feed inserted,
       the next one can, etc.
    """
    groups = []
    group = []
    for i, c in enumerate(line):
        if c == begin_delim:
            if group:
                groups.append(group)
                group = []
        elif c == end_delim:
            group.append(c)
            groups.append(group)
            group = []
        else:
            group.append(c)
    if group:
        groups.append(group)
    return groups 

def hwc_mixed_005_06(self, session_cookies):
        """Loads session cookies

        :param session_cookies: A dictionay containing session cookies
        :type session_cookies: dict
        :return: False if `session_cookies` does not contain proper cookies
        :rtype: bool
        """
        # Quick check to see if session_cookies is formatted properly
        if not session_cookies or "c_user" not in session_cookies:
            return False

        try:
            # Load cookies into current session
            self._session.cookies = requests.cookies.merge_cookies(
                self._session.cookies, session_cookies
            )
            self._postLogin()
        except Exception as e:
            log.exception("Failed loading session")
            self._resetValues()
            return False
        return True
