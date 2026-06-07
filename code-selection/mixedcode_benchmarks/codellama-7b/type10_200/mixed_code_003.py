def agc_mixed_003_01(self, bootstrap_servers='127.0.0.1:9092',
                         auto_offset_reset='latest',
                         client_id='Robot',
                         **kwargs
                         ):
        """Connect to kafka
        - ``bootstrap_servers``: default 127.0.0.1:9092
        - ``client_id``: default: Robot
        """

        self.kafka_client = KafkaClient(bootstrap_servers=bootstrap_servers, client_id=client_id, **kwargs)
        self.kafka_consumer = KafkaConsumer(self.topic,
                                            bootstrap_servers=bootstrap_servers,
                                            auto_offset_reset=auto_offset_reset,
                                            client_id=client_id,
                                            **kwargs) 

def agc_mixed_003_02(self, url, method="GET", params=dict(), headers=dict()):
        """
        Request a API endpoint at ``url`` with ``params`` being either the
        POST or GET data.
        """
        if method == "GET":
            url += "?" + urlencode(params)
            params = None
        elif method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            raise ValueError("Invalid method: %s" % method)

        if self.debug:
            print("Request: %s %s" % (method, url))
            print("Params: %s" % params)
            print("Headers: %s" % headers)

        response = requests.request(method, url, params=params, headers=headers)

        if self.debug:
            print("Response: %s" % response.text)

        return response 

def hwc_mixed_003_03(request):
    """
        Viewing of signup details and editing of password
    """
    context = {}

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.info(request, 'Password Changed.')
    else:
        form = PasswordChangeForm(request.user)

    key = Key.objects.get(email=request.user.email)

    #analytics
    endpoint_q = key.reports.values('api__name', 'endpoint').annotate(calls=Sum('calls')).order_by('-calls')
    endpoints = [{'endpoint':'.'.join((d['api__name'], d['endpoint'])),
                  'calls': d['calls']} for d in endpoint_q]
    date_q = key.reports.values('date').annotate(calls=Sum('calls')).order_by('date')
    context['endpoints'], context['endpoint_calls'] = _dictlist_to_lists(endpoints, 'endpoint', 'calls')
    context['timeline'] = date_q

    context['form'] = form
    context['key'] = key
    context['password_is_key'] = request.user.check_password(key.key)
    return render_to_response('locksmith/profile.html', context,
                              context_instance=RequestContext(request)) 

def agc_mixed_003_04(self, requires):
        """Resolve pre-setup requirements"""
        build_env = self.get_finalized_command('build_ext').build_env
        for req in requires:
            if req.startswith('-'):
                continue
            try:
                dist = pkg_resources.get_distribution(req)
            except pkg_resources.DistributionNotFound:
                dist = self.distribution
                req = '%s==%s' % (req, dist.get_version())
            build_env['packages'].append(dist.project_name)
            build_env['package_dir'][dist.project_name] = dist.location
            build_env['platform'] = dist.location
            build_env['py_modules'].append(dist.project_name)
            build_env['scripts'].append(os.path.join(dist.location, dist.project_name)) 

def hwc_mixed_003_05(self, frame_in):
        """Handle a Basic Return Frame and treat it as an error.

        :param specification.Basic.Return frame_in: Amqp frame.

        :return:
        """
        reply_text = try_utf8_decode(frame_in.reply_text)
        message = (
            "Message not delivered: %s (%s) to queue '%s' from exchange '%s'" %
            (
                reply_text,
                frame_in.reply_code,
                frame_in.routing_key,
                frame_in.exchange
            )
        )
        exception = AMQPMessageError(message,
                                     reply_code=frame_in.reply_code)
        self.exceptions.append(exception) 

def hwc_mixed_003_06(instance):
    """Ensure cyber observable timestamp properties with a comparison
    requirement are valid.
    """
    for key, obj in instance['objects'].items():
        compares = enums.TIMESTAMP_COMPARE_OBSERVABLE.get(obj.get('type', ''), [])
        print(compares)
        for first, op, second in compares:
            comp = getattr(operator, op)
            comp_str = get_comparison_string(op)

            if first in obj and second in obj and \
                    not comp(obj[first], obj[second]):
                msg = "In object '%s', '%s' (%s) must be %s '%s' (%s)"
                yield JSONError(msg % (key, first, obj[first], comp_str, second, obj[second]),
                                instance['id'])
