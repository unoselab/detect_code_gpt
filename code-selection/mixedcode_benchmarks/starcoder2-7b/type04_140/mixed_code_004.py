async def hwc_mixed_004_01(self,
                           request: Request,
                           message: BaseMessage,
                           responder: Responder) \
            -> Tuple[
                Optional[BaseState],
                Optional[BaseTrigger],
                Optional[bool],
            ]:
        """
        Build the state for this request.
        """

        trigger, state_class, dnr = await self._find_trigger(request)

        if trigger is None:
            if not message.should_confuse():
                return None, None, None
            state_class = self._confused_state(request)
            logger.debug('Next state: %s (confused)', state_class.name())
        else:
            logger.debug('Next state: %s', state_class.name())

        state = state_class(request, responder, trigger, trigger)
        return state, trigger, dnr 

def hwc_mixed_004_02(self, destination, message, add_path_step):
        """Factory function to generate independent message objects for
        downstream recipients with different destinations."""
        if add_path_step and self.recipe_pointer:
            recipe_path = self.recipe_path + [self.recipe_pointer]
        else:
            recipe_path = self.recipe_path

        return {
            "environment": self.environment,
            "payload": message,
            "recipe": self.recipe.recipe,
            "recipe-path": recipe_path,
            "recipe-pointer": destination,
        } 

def agc_mixed_004_03(db_dir, records='all'):
    """
    Get a list of records belonging to a database.

    Parameters
    ----------
    db_dir : str
        The database directory, usually the same as the database slug.
        The location to look for a RECORDS file.
    records : list, optional
        A Option used when this function acts as a helper function.
        Leave as default 'all' to get all records.

    Examples
    --------
    >>> wfdb.get_record_list('mitdb')

    """
    # Full url physiobank database
    records_file = os.path.join(db_dir, 'RECORDS')
    if not os.path.isfile(records_file):
        raise IOError('No RECORDS file found in %s' % db_dir)
    with open(records_file, 'r') as f:
        records = f.read().splitlines()
    if records == ['']:
        records = []
    if records == ['all']:
        records = [os.path.splitext(f)[0] for f in os.listdir(db_dir)
                   if os.path.isfile(os.path.join(db_dir, f))
                   and f.endswith('.hea')]
    return records 

def agc_mixed_004_04(message):
    """Send a message to the slack channel #coretools"""

    slack_token = os.environ.get('SLACK_TOKEN')
    slack_channel = os.environ.get('SLACK_CHANNEL')
    slack_webhook = os.environ.get('SLACK_WEBHOOK')
    if slack_token and slack_channel and slack_webhook:
        slack_client = SlackClient(slack_token)
        slack_client.api_call(
            "chat.postMessage",
            channel=slack_channel,
            text=message,
            username='coretools',
            icon_emoji=':robot_face:'
        )
    else:
        print("Slack token, channel and webhook not set") 

def hwc_mixed_004_05(self, e, pair):
        """Called for pairs that don't match `match` and `exclude` filters."""
        RED = ansi_code("Fore.LIGHTRED_EX")
        R = ansi_code("Style.RESET_ALL")
        # any_entry = pair.any_entry
        write((RED + "ERROR: {}\n    {}" + R).format(e, pair))
        # Return True to ignore this error (instead of raising and terminating the app)
        if "[Errno 92] Illegal byte sequence" in "{}".format(e) and compat.PY2:
            write(RED + "This _may_ be solved by using Python 3." + R)
            # return True
        return False 

def agc_mixed_004_06(self, expires_in=None):
        """
        Create a secure timed JWT token that can be passed. It save the user id,
        which later will be used to retrieve the data

        :param user: AuthUser, the user's object
        :param expires_in: - time in second for the token to expire
        :return: string
        """
        if not expires_in:
            expires_in = self.JWT_EXPIRATION_DELTA.total_seconds()

        payload = {
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow(),
           'sub': self.user.id
        }

        return jwt.encode(
            payload,
            self.JWT_SECRET,
            algorithm='HS256'
        ).decode('utf-8')
