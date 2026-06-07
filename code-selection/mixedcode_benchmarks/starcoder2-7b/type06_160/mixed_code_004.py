def hwc_mixed_004_01(self, motor, speed):
        """
        Change the speed of a motor on the controller.

        :param motor: The motor to change.
        :type motor: ``int``

        :param speed: Speed from -100 to +100, 0 is stop
        :type speed: ``int``

        """
        self._validate_motor(motor)
        en, in1, in2 = self._motors[motor-1]

        if speed == 0:
            en.pwm_stop()
            in1.set(False)
            in2.set(False)
        elif speed > 0:
            en.pwm_start(abs(speed))
            in1.set(True)
            in2.set(False)
        else:
            en.pwm_start(abs(speed))
            in1.set(False)
            in2.set(True) 

def agc_mixed_004_02(dim_vars, reverse_map=False):
    """
    axis name       -> [dimension names]
    dimension name  -> [axis_name], length 0 if reverse_map
    """
    axes = {}
    for dim_var in dim_vars:
        if dim_var.name in axes:
            raise ValueError("Duplicate dimension name: %s" % dim_var.name)
        axes[dim_var.name] = []
    for dim_var in dim_vars:
        for axis_name in dim_var.axis:
            if axis_name not in axes:
                raise ValueError("Unknown axis name: %s" % axis_name)
            axes[axis_name].append(dim_var.name)
    if reverse_map:
        return {dim_name: axes[dim_name] for dim_name in axes}
    else:
        return axes 

def hwc_mixed_004_03(eval_sentences, ref_sentences, n=2):
  """Computes ROUGE-N f1 score of two text collections of sentences.

  Source: https://www.microsoft.com/en-us/research/publication/
  rouge-a-package-for-automatic-evaluation-of-summaries/

  Args:
    eval_sentences: Predicted sentences.
    ref_sentences: Sentences from the reference set
    n: Size of ngram.  Defaults to 2.

  Returns:
    f1 score for ROUGE-N
  """
  f1_scores = []
  for eval_sentence, ref_sentence in zip(eval_sentences, ref_sentences):
    eval_ngrams = _get_ngrams(n, eval_sentence)
    ref_ngrams = _get_ngrams(n, ref_sentence)
    ref_count = len(ref_ngrams)
    eval_count = len(eval_ngrams)

    # Count the overlapping ngrams between evaluated and reference
    overlapping_ngrams = eval_ngrams.intersection(ref_ngrams)
    overlapping_count = len(overlapping_ngrams)

    # Handle edge case. This isn't mathematically correct, but it's good enough
    if eval_count == 0:
      precision = 0.0
    else:
      precision = float(overlapping_count) / eval_count
    if ref_count == 0:
      recall = 0.0
    else:
      recall = float(overlapping_count) / ref_count
    f1_scores.append(2.0 * ((precision * recall) / (precision + recall + 1e-8)))

  # return overlapping_count / reference_count
  return np.mean(f1_scores, dtype=np.float32) 

def agc_mixed_004_04(self, time_zone='', include_day=True, include_time=True):

        """ a method to report a human friendly string from a labDT object

        :param time_zone: [optional] string with timezone to report in
        :return: string with date and time info
        """

    # validate inputs
        if include_day:
            date_string = self.date.strftime('%A, %B %d, %Y')
        else:
            date_string = self.date.strftime('%B %d, %Y')

        if include_time:
            time_string = self.time.strftime('%I:%M %p')
        else:
            time_string = ''

        if time_zone == '':
            return date_string +'' + time_string
        else:
            return date_string +'' + time_string +'' + time_zone 

def hwc_mixed_004_05(self, form, field):
        """Ensure that Usernames contains at least 3 alphanumeric characters.

        Override this method to customize the username validator.
        """
        username = field.data
        if len(username) < 3:
            raise ValidationError(
                _('Username must be at least 3 characters long'))
        valid_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._'
        chars = list(username)
        for char in chars:
            if char not in valid_chars:
                raise ValidationError(
                    _("Username may only contain letters, numbers, '-', '.' and '_'")) 

def agc_mixed_004_06(self, gcloud_zone, page_token=None):
        """ Generator function which yields ResourceRecordSet for the managed
            gcloud zone, until there are no more records to pull.

            :param gcloud_zone: zone to pull records from
            :type gcloud_zone: google.cloud.dns.ManagedZone
            :param page_token: page token for the page to get

            :return: a resource record set
            :type return: google.cloud.dns.ResourceRecordSet
        """
        records = gcloud_zone.list_resource_record_sets(page_token=page_token)

        # Yield each record
        for record in records:
            yield record

        # If there are more pages, get them
        if records.next_page_token:
            for record in self._get_gcloud_records(gcloud_zone,
                                                   records.next_page_token):
                yield record
