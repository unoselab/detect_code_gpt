def hwc_mixed_004_01(self, spec_or_id=None, multi=True, **kwargs):
        """Remove a document(s) from this collection.

        **DEPRECATED** - Use :meth:`delete_one` or :meth:`delete_many` instead.

        .. versionchanged:: 3.0
           Removed the `safe` parameter. Pass ``w=0`` for unacknowledged write
           operations.
        """
        warnings.warn("remove is deprecated. Use delete_one or delete_many "
                      "instead.", DeprecationWarning, stacklevel=2)
        if spec_or_id is None:
            spec_or_id = {}
        if not isinstance(spec_or_id, abc.Mapping):
            spec_or_id = {"_id": spec_or_id}
        write_concern = None
        collation = validate_collation_or_none(kwargs.pop('collation', None))
        if kwargs:
            write_concern = WriteConcern(**kwargs)
        return self._delete_retryable(
            spec_or_id, multi, write_concern, collation=collation) 

def agc_mixed_004_02(self, message):
        """
        A helper method that does the actual sending

        :param SmsMessage message: SmsMessage class instance.
        :returns: True if message is sent else False
        :rtype: bool
        """

        if not isinstance(message, SmsMessage):
            raise TypeError("message must be a SmsMessage instance")

        if not message.validate():
            raise ValueError("message is not valid")

        if self.debug:
            print("Sending message: %s" % message)

        try:
            response = self._send_request(message)
        except Exception as e:
            raise SmsException(e)

        if not response.ok:
            raise SmsException(response.text)

        return True 

def hwc_mixed_004_03(canvas, fn, delay=1./24, *args, **kwargs):
    """Animation automation function

    :param canvas: :class:`Canvas` object
    :param fn: Callable. Frame coord generator
    :param delay: Float. Delay between frames.
    :param *args, **kwargs: optional fn parameters
    """

    # python2 unicode curses fix
    if not IS_PY3:
        import locale
        locale.setlocale(locale.LC_ALL, "")

    def animation(stdscr):

        for frame in fn(*args, **kwargs):
            for x,y in frame:
                canvas.set(x,y)

            f = canvas.frame()
            stdscr.addstr(0, 0, '{0}\n'.format(f))
            stdscr.refresh()
            if delay:
                sleep(delay)
            canvas.clear()

    curses.wrapper(animation) 

def agc_mixed_004_04(self, definitions, field, value):
        """ {'type': 'list', 'logical': 'allof'} """
        if not isinstance(value, list):
            raise ValidationError(
                "Value must be a list",
                field,
                value,
                definitions,
                self.name,
            )
        for item in value:
            self._validate_type(definitions, field, item)
        return value 

def hwc_mixed_004_05(self):
        """
        Return cached repo metadata
        """
        cache = salt.cache.Cache(self.opts, self.opts['spm_cache_dir'])
        metadata = {}

        def _read_metadata(repo, repo_info):
            if cache.updated('.', repo) is None:
                log.warning('Updating repo metadata')
                self._download_repo_metadata({})

            metadata[repo] = {
                'info': repo_info,
                'packages': cache.fetch('.', repo),
            }

        self._traverse_repos(_read_metadata)
        return metadata 

def agc_mixed_004_06(sender, receivers, subject, text=None, html=None, charset='utf-8', config=Injected):
    """Sends an email.

    :param sender: Sender as string or None for default got from config.
    :param receivers: String or array of recipients.
    :param subject: Subject.
    :param text: Plain text message.
    :param html: Html message.
    :param charset: Charset.
    :param config: Current configuration
    """
    if not isinstance(receivers, list):
        receivers = [receivers]

    if not sender:
        sender = config.email_sender

    if not text:
        text = ''

    if not html:
        html = ''

    if not isinstance(sender, list):
        sender = [sender]

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender[0]
    msg['To'] = ', '.join(receivers)
    msg.attach(MIMEText(text, 'plain', charset))
    msg.attach(MIMEText(html, 'html', charset))

    smtp = smtplib.SMTP(config.email_host, config.email_port)
    smtp.ehlo()
    smtp.starttls()
    smtp.login(config.email_user, config.email_password)
    smtp.sendmail(sender[0], receivers, msg.as_string())
    smtp.close()
