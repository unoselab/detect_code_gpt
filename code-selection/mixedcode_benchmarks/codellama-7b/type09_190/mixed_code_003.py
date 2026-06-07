def hwc_mixed_003_01(cls, _dict):
        """Initialize a LogCollection object from a json dictionary."""
        args = {}
        if 'logs' in _dict:
            args['logs'] = [Log._from_dict(x) for x in (_dict.get('logs'))]
        else:
            raise ValueError(
                'Required property \'logs\' not present in LogCollection JSON')
        if 'pagination' in _dict:
            args['pagination'] = LogPagination._from_dict(
                _dict.get('pagination'))
        else:
            raise ValueError(
                'Required property \'pagination\' not present in LogCollection JSON'
            )
        return cls(**args) 

def hwc_mixed_003_02(self, connection, event):
        """
        event.arguments[0] == "@" for secret channels,
                          "*" for private channels,
                          "=" for others (public channels)
        event.arguments[1] == channel
        event.arguments[2] == nick list
        """

        ch_type, channel, nick_list = event.arguments

        if channel == '*':
            # User is not in any visible channel
            # http://tools.ietf.org/html/rfc2812#section-3.2.5
            return

        for nick in nick_list.split():
            nick_modes = []

            if nick[0] in self.connection.features.prefix:
                nick_modes.append(self.connection.features.prefix[nick[0]])
                nick = nick[1:]

            for mode in nick_modes:
                self.channels[channel].set_mode(mode, nick)

            self.channels[channel].add_user(nick) 

def agc_mixed_003_03(self, filetype, base_dir=None, sasdir='sas', **kwargs):
        """Return the url of a given type of file.

        Parameters
        ----------
        filetype : str
            File type parameter.

        Returns
        -------
        full : str
            The sas url to the file.
        """

        if base_dir is None:
            base_dir = self.base_dir
        if base_dir is None:
            raise ValueError('No base_dir provided')
        if sasdir is None:
            sasdir = self.sasdir
        if sasdir is None:
            raise ValueError('No sasdir provided')
        if filetype not in self.filetypes:
            raise ValueError('Filetype not supported')
        if filetype == 'sas':
            return base_dir + '/' + sasdir
        else:
            return base_dir + '/' + sasdir + '/' + filetype 

def agc_mixed_003_04(self, arn, event_time, tech, item=None):
        """Dumps the proper JSON for the schema. If the event is too big, then don't include the item.

        :param arn:
        :param event_time:
        :param tech:
        :param item:
        :return:
        """
        if item is None:
            return {
                'arn': arn,
                'event_time': event_time,
                'tech': tech
            }
        else:
            return {
                'arn': arn,
                'event_time': event_time,
                'tech': tech,
                'item': item
            } 

def hwc_mixed_003_05(self):
        """Complete daily mission then get the money."""
        response = self.session.get(self.mission_url, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        onclick = soup.find('input', class_='super normal button')['onclick']
        url = onclick.split('=', 1)[1][2:-2]

        if url == '/balance':
            return "You have completed the mission today."
        else:
            headers = {'Referer': 'https://www.v2ex.com/mission/daily'}
            data = {'once': url.split('=')[-1]}
            self.session.get('https://www.v2ex.com'+url, verify=False,
                             headers=headers, data=data)
            balance = self._get_balance()
            return balance 

def agc_mixed_003_06(log_level, log_file=None, logger_name=None):
        """setup logger
            @param log_level: debug/info/warning/error/critical
            @param log_file: log file path
            @param logger_name: the name of logger, default is 'root' if not specify
        """
        if logger_name is None:
            logger_name = 'root'
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)

        if log_file is not None:
            fh = logging.FileHandler(log_file)
            fh.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        return logger
