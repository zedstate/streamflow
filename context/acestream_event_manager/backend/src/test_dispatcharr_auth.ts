import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const BASE_URL = process.env.DISPATCHARR_URL;
const USERNAME = process.env.DISPATCHARR_USER;
const PASSWORD = process.env.DISPATCHARR_PASS;

console.log('Testing Dispatcharr API (JWT Mode)...');

async function testApi() {
    try {
        // 1. Obtain Token
        console.log('\n--- Attempting Token Obtain ---');
        const tokenUrl = `${BASE_URL}/api/accounts/token/`;
        console.log('POST', tokenUrl);

        const tokenRes = await axios.post(tokenUrl, {
            username: USERNAME,
            password: PASSWORD,
        });

        console.log('Token Status:', tokenRes.status);
        console.log('Token Response Keys:', Object.keys(tokenRes.data));

        const accessToken = tokenRes.data.access;
        console.log('Access Token:', accessToken ? 'Found' : 'MISSING');

        if (!accessToken) {
            console.error('No access token received!');
            console.log('Full Response:', JSON.stringify(tokenRes.data, null, 2));
            return;
        }

        // 2. Fetch Channels
        console.log('\n--- Attempting Fetch Channels ---');
        const channelsUrl = `${BASE_URL}/api/channels/channels/?page_size=10`;
        console.log('GET', channelsUrl);

        const chanRes = await axios.get(channelsUrl, {
            headers: {
                Authorization: `Bearer ${accessToken}`
            }
        });
        console.log('Channels Status:', chanRes.status);
        console.log('Channels Response Keys:', Object.keys(chanRes.data));

        if (chanRes.data.results) {
            console.log('Number of channels (first page):', chanRes.data.results.length);
            if (chanRes.data.results.length > 0) {
                console.log('Sample Channel:', JSON.stringify(chanRes.data.results[0], null, 2));
            }
        }

    } catch (err: any) {
        console.error('Operation Failed!');
        if (err.response) {
            console.error('Status:', err.response.status);
            console.error('Data:', JSON.stringify(err.response.data, null, 2));
        } else {
            console.error(err);
        }
    }
}

testApi();
