function messagesFetched()
{
    document.getElementById('messages').innerHTML = this.responseText;
    MathJax.Hub.Queue(["Typeset",MathJax.Hub], [window.setTimeout, 'fetchMessages()', 3000]);
}

function smiliesFetched()
{
    document.getElementById('smilies').innerHTML = this.responseText;
}

function hideSmilies()
{
    document.getElementById('smilies').innerHTML = '<button type="button" onclick="fetchSmilies()">Smile!</button>';
}

function smileyClicked(smiley)
{
    var re = /(^|\s)$/;
    var val = document.getElementById('messageinput').value;
    if (!re.test(val))
    {
        // message doesn't end with whitespace; add a space
        val += ' ';
    }
    val += smiley;
    document.getElementById('messageinput').value = val;
}

function fetchMessages()
{
    var req = new XMLHttpRequest();
    req.onload = messagesFetched;
    req.open('GET', '/messages', true);
    req.send();
}

function fetchSmilies()
{
    var req = new XMLHttpRequest();
    req.onload = smiliesFetched;
    req.open('GET', '/smilies', true);
    req.send();
}

function sendQuick(msg)
{
    var req = new XMLHttpRequest();
    var body = "message=" + encodeURIComponent(msg);
    req.open('POST', '/postmessage', true);
    req.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    req.setRequestHeader('Content-Length', body.length);
    req.setRequestHeader('Connection', 'close');
    req.send(body);
}

function resizableTextAreaKeyPress(event)
{
    if (event.keyCode == 13 && !event.shiftKey)
    {
        this.form.submit();
        event.preventDefault();
    }
    this.style.height = '10px';
    this.style.height = this.scrollHeight + 6 + 'px';
}

function markTextAreaAsResizableEnterSubmit(id)
{
    document.getElementById(id).addEventListener('keydown', resizableTextAreaKeyPress);
}
