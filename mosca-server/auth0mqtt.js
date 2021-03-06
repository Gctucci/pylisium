/**
 * Based on the Auth0 post: https://auth0.com/docs/integrations/authenticating-devices-using-mqtt
 * Based on code deloped by @eugenioip in Github: https://github.com/eugeniop/auth0mosca
 */
var request = require('request');
var jwt = require('jsonwebtoken');

function Auth0Mosca(auth0Namespace, clientId, clientSecret, connection, clientAudience, clientIssuer) {
    this.auth0Namespace = auth0Namespace;
    this.connection = connection;
    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.clientAudience = clientAudience;
    this.clientIssuer = clientIssuer;
}

Auth0Mosca.prototype.authenticateWithJWT = function () {

    var self = this;

    return function (client, username, password, callback) {

        if (username !== 'JWT') {
            return callback("Invalid Credentials", false);
        }

        // console.log('Passsord:'+password);

        jwt.verify(
            password.toString(),
            self.clientSecret, {
            audience: self.clientAudience,
            issuer: self.clientIssuer,
            algorithms: ['HS256']
        }, function (err, profile) {
            if (err) {
                console.log(err);
                return callback("Error getting UserInfo", false);
            }
            console.log("Authenticated client " + profile.user_id);
            console.log(profile.topics);
            client.deviceProfile = profile;
            return callback(null, true);
        });
    };
};

Auth0Mosca.prototype.authenticateWithCredentials = function () {

    var self = this;

    return function (client, username, password, callback) {

        var data = {
            client_id: self.clientId, // {client-name}
            username: username.toString(),
            password: password.toString(),
            connection: self.connection,
            grant_type: "password",
            scope: 'openid name email' //Details: https:///scopes
        };

        request.post({
            headers: {
                "Content-type": "application/json"
            },
            url: self.auth0Namespace + '/oauth/ro',
            body: JSON.stringify(data)
        }, function (e, r, b) {
            if (e) {
                console.log('Error in Authentication');
                return callback(e, false);
            }
            var r = JSON.parse(b);

            if (r.error) {
                return callback(r, false);
            }

            jwt.verify(r.id_token, self.clientSecret, function (err, profile) {
                if (err) {
                    return callback("Error getting UserInfo", false);
                }
                client.deviceProfile = profile;
                return callback(null, true);
            });
        });
    };
};

Auth0Mosca.prototype.authorizePublish = function () {
    return function (client, topic, payload, callback) {
        if (client.deviceProfile.topics !== undefined) {
            callback(null, client.deviceProfile && client.deviceProfile.topics && client.deviceProfile.topics.indexOf(topic) > -1);
        } else {
            callback(null, topic.toString().indexOf(client.id.toString()) > -1);
        }
    };
};

Auth0Mosca.prototype.authorizeSubscribe = function () {
    return function (client, topic, callback) {
        callback(null, true);
    };
}

module.exports = Auth0Mosca;