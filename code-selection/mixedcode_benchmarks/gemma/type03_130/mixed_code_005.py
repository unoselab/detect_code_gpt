def agc_mixed_005_01(self, actor, exc=None, exit_code=None):
        """Gracefully stop the ``actor``.
        """
        if actor.state == 'stopped':
            return

        if exc:
            actor.exception = exc
        elif exit_code is not None:
            actor.exit_code = exit_code

        actor.state = 'stopping'
        actor.stop_event.set()

        if actor.task:
            actor.task.cancel()

        actor.state = 'stopped' 

def hwc_mixed_005_02(readme_file):
    """ Read package long description from README file """
    try:
        import pypandoc
    except (ImportError, OSError) as e:
        print('No pypandoc or pandoc: %s' % (e,))
        if is_py3:
            fh = open(readme_file, encoding='utf-8')
        else:
            fh = open(readme_file)
        long_description = fh.read()
        fh.close()
        return long_description
    else:
        return pypandoc.convert(readme_file, 'rst') 

def agc_mixed_005_03(client, datasets):
    """Format datasets with a tabular output."""
    for dataset in datasets:
        if not dataset:
            continue
        headers = dataset[0].keys()
        header_row = " | ".join(headers)
        separator = "-+-".join(["-" * len(h) for h in headers])
        print(header_row)
        print(separator)
        for row in dataset:
            print(" | ".join(str(row.get(h, "")) for h in headers))
        print() 

def hwc_mixed_005_04(self, attrs):
        """ checks if login credentials are correct """
        user = authenticate(**self.user_credentials(attrs))

        if user:
            if user.is_active:
                self.instance = user
            else:
                raise serializers.ValidationError(_("This account is currently inactive."))
        else:
            error = _("Invalid login credentials.")
            raise serializers.ValidationError(error)
        return attrs 

def agc_mixed_005_05(self, athlete_id=None, limit=None):
        """
        Gets friends for current (or specified) athlete.

        http://strava.github.io/api/v3/follow/#friends

        :param: athlete_id
        :type: athlete_id: int

        :param limit: Maximum number of athletes to return (default unlimited).
        :type limit: int

        :return: An iterator of :class:`stravalib.model.Athlete` objects.
        :rtype: :class:`BatchedResultsIterator`
        """
        params = {}
        if athlete_id:
            params['id'] = athlete_id
        if limit:
            params['limit'] = limit

        return self._get_batched_results(
            'athlete', 
            'friends', 
            params=params, 
            model=Athlete
        ) 

def hwc_mixed_005_06(function=None):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary.
    """
    def check_perms(user):
        # if user not logged in, show login form
        if not user.is_authenticated:
            return False
        # if this is the admin site only admin access
        if settings.ADMIN_REQUIRED and not user.is_admin:
            raise PermissionDenied
        return True

    actual_decorator = user_passes_test(check_perms, login_url=_login_url)
    if function:
        return actual_decorator(function)
    return actual_decorator
