/**
 * Utility functions related to the front-end.
 */

(function() {

    Utils = function(timestamp, contest_start, contest_stop, phase)
    {
        this.last_notification = timestamp;
        this.timestamp = timestamp;
        this.contest_start = contest_start;
        this.contest_stop = contest_stop;
        this.phase = phase;
    }

    Utils.prototype =
    {

        /**
         * To be added to the onclick of an element named
         * title_XXX. Hide/show an element named XXX, and change the class
         * of title_XXX between toggling_on and toggling_off
         */
        toggle_visibility: function(item_id)
        {
            var item = document.getElementById(item_id);
            var title = document.getElementById("title_" + item_id);
            if (item.style.display != "none")
            {
                title.className = item.className.replace(/\btoggling_on\b/, '');
                title.className += ' toggling_off';
                item.style.display = "none"
            }
            else
            {
                title.className = item.className.replace(/\btoggling_off\b/, '');
                title.className += ' toggling_on';
                item.style.display = "block"
            }
        },

        /**
         * Display the notification to the user.
         *
         * type (string): can be "notification", "message", "question",
         *                "announcement".
         * timestamp (int): time of the notification.
         * subject (string): subject.
         * text (string): body of notification.
         */
        display_notification: function(type, timestamp, subject, text)
        {
            if (this.last_notification < timestamp)
                this.last_notification = timestamp;
            var div = document.getElementById("notifications");
            var s = '<div class="notification">' +
                '<div class="notification_close" ' +
                'onclick="utils.close_notification(this);">&times;' +
                '</div><div class="notification_msg">' +
                '<div class="notification_timestamp">' +
                this.format_time_or_date(timestamp) +
                '</div>';

            s += '<div class="notification_subject">'
            if (type == "message")
                s += 'Private message. ';
            else if (type == "announcement")
                s += 'Announcement. ';
            else if (type == "question")
                s += 'Reply to your question. ';

            s += subject + '</div>';
            s += '<div class="notification_text">' + text + '</div>';
            s += '</div></div>'
            div.innerHTML += s;
        },

        /**
         * Ask CWS (via ajax, not rpc) to send to the user the new
         * notifications.
         */
        update_notifications: function()
        {
            display_notification = cmsutils.bind_func(this,
                                                      this.display_notification);
            cmsutils.ajax_request("/notifications",
                                  "last_notification=" + this.last_notification,
                                  function(response)
                                  {
                                      response = JSON.parse(response);
                                      for (var i = 0; i < response.length; i++)
                                          display_notification(
                                              response[i].type,
                                              parseInt(response[i].timestamp),
                                              response[i].subject,
                                              response[i].text);
                                  });
        },

        /**
         * For the close button of a notification.
         */
        close_notification: function(item)
        {
            item.parentNode.parentNode.removeChild(item.parentNode);
        },

        /**
         * Update the remaining time showed in the "remaining" div.
         */
        get_time: function()
        {
            if (this.contest_stop != null)
                var sec_to_end = this.contest_stop - this.timestamp ;
            else
                var sec_to_end = Infinity;

            if (this.contest_start != null)
                var sec_to_start = this.contest_start - this.timestamp;
            else
                var sec_to_start = -Infinity;

            var now = new Date();

            var nowsec_to_end = sec_to_end - (now - firstDate) / 1000;
            var nowsec_to_start = sec_to_start - (now - firstDate) / 1000;
            if ((nowsec_to_end <= 0 && this.phase == 0 ) ||
                (nowsec_to_start <= 0 && this.phase == -1 ))
                window.location.href = "/";

            countdown = nowsec_to_end;

            if ( this.phase == -1 )
                countdown = nowsec_to_start;

            var hours = countdown / 60 / 60;
            var hoursR = Math.floor(hours);
            var minutes = countdown / 60 - (60*hoursR);
            var minutesR = Math.floor(minutes);
            var seconds = countdown - (60*60*hoursR) - (60*minutesR);
            var secondsR = Math.floor(seconds);
            if (minutesR < 10) m = "0" + minutesR;
            else m = minutesR;
            if (secondsR < 10) s = "0" + secondsR;
            else s = secondsR;

            if (document.getElementById("remaining"))
                document.getElementById("remaining").innerHTML = hoursR+":"+m+":"+s;
        },

        /**
         * Represent in a nice looking way a couple (job_type,
         * submission_id) coming from the backend.
         *
         * job (array): a couple (job_type, submission_id)
         * returns (string): nice representation of job
         */
        repr_job: function(job)
        {
            var job_type = "???";
            if (job == null)
                return "N/A";
            else if (job == "disabled")
                return "Worker disabled";
            else if (job[0] == 'compile')
                job_type = 'Compiling';
            else if (job[0] == 'evaluate')
                job_type = 'Evaluating';
            var submission_link = '<a href="/submissions/details/' + job[1] + '">';
            return job_type + ' submission ' + submission_link + job[1] + '</a>';
        },

        /**
         * Format time as hours, minutes and seconds ago.
         *
         * time (int): a unix time.
         * returns (string): nice representation of time as "x time
         *                   ago"
         */
        repr_time_ago: function(time)
        {
            if (time == null)
                return "N/A";
            var diff = datetime = parseInt((new Date()).getTime()/1000 - time);
            var res = "";

            var s = diff % 60;
            diff = diff - s;
            res = s + " second(s)";
            if (diff == 0)
                return res;
            diff /= 60;

            var m = diff % 60;
            diff -= m;
            res = m + " minute(s), " + res;
            if (diff == 0)
                return res;
            diff /= 60;

            var h = diff;
            res = h + " hour(s), " + res;
            return res;
        },

        /**
         * Return timestamp formatted as HH:MM:SS.
         *
         * timestamp (int): unix time.
         * return (string): timestamp formatted as above.
         */
        format_time: function(timestamp)
        {
            var date = new Date(timestamp * 1000);
            var hours = date.getHours();
            if (hours < 10)
                hours = "0" + hours;
            var minutes = date.getMinutes();
            if (minutes < 10)
                minutes = "0" + minutes;
            var seconds = date.getSeconds();
            if (seconds < 10)
                seconds = "0" + seconds;
            return hours + ":" + minutes + ":" + seconds;

        },

        /**
         * Return timestamp formatted as dd/mm/yyyy HH:MM:SS.
         *
         * timestamp (int): unix time.
         * return (string): timestamp formatted as above.
         */
        format_datetime: function(timestamp)
        {
            var time = this.format_time(timestamp);
            var date = new Date(timestamp * 1000);
            var days = date.getDate();
            if (days < 10)
                days = "0" + days;
            var months = date.getMonth() + 1; // months are 0-11
            if (months < 10)
                months = "0" + months;
            var years = date.getFullYear();
            return days + "/" + months + "/" + years + " " + time;

        },

        /**
         * Return timestamp formatted as HH:MM:SS if the date is the
         * same date as today, as a complete date + time if the date
         * is different.
         *
         * timestamp (int): unix time.
         * return (string): timestamp formatted as above.
         */
        format_time_or_date: function(timestamp)
        {
            var today = (new Date()).toDateString();
            var date = new Date(timestamp * 1000);
            if (today == date.toDateString())
                return this.format_time(timestamp);
            else
                return this.format_datetime(timestamp);
        },

        switch_contest: function()
        {
            var select = document.getElementById("contest_selection_select")
            var value = select.options[select.selectedIndex].value
            if (value == "null")
                window.location = "/";
            else
                window.location = "/contest/" + value;
        }

    };
}());
