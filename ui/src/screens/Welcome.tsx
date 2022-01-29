import { AxiosResponse } from 'axios'
import React, { FC, useState } from 'react'
import { useHistory } from 'react-router-dom'
import {
    Button,
    Form,
    Input,
    Loader,
    Container,
    Grid,
    Dimmer,
    Segment,
    Message,
    Divider
} from 'semantic-ui-react'
import server from '../utils/server'
import logo from '../images/OSU_horizontal_2C_O_over_B.png'

interface WelcomeProps {}

export const Welcome: FC<WelcomeProps> = () => {

    const [processing, setProcessing] = useState<boolean>(false)
    const [email, setEmail] = useState<string>('')

    const history = useHistory()

    /**
     * Handle a press of the Get Started button
     */
    const handleGetStarted = async () => {
        setProcessing(true) // show processing indicator
        const response: AxiosResponse = await server.post(
            '/start',
            { email }
        ) // initialize the user in the backend and retrieve the user's scenarios
        const scenarios = response.data.scenarios
        if (response.status === 201 || scenarios.length === 5) {
            // New user; take them to the Start page
            history.push('/start', { email, scenarios, status: 'begin' })
        } else if (response.status === 200) {
            // Returning user; let them resume their work
            alert(`Welcome back! You have ${scenarios.length} datasets left to go.`)
            history.push('/start', { email, scenarios, status: 'resume'})
        }
    }

    return (
        <Dimmer.Dimmable as={Segment} dimmed={processing}>
            <Grid centered stretched={false} columns={1} className='site-page home'>
                <Grid.Column>
                    <Grid.Row className='content-centered'>
                        <Container className='section' style={{ backgroundColor: 'white', position: 'absolute', top: 0, right: 0, width: '10vw', maxWidth: '500px', height: '8vh', borderBottomLeftRadius: 20 }} >
                            <img src={logo} style={{ padding: 10, position: 'absolute', top: 0, right: 0, width: '100%', height: 'auto' }} alt='OSU logo' />
                        </Container> 
                        <Container className='home-header box-blur'>
                            <span className='home-title'>Discovering Patterns in Data</span>
                        </Container>
                    </Grid.Row>
                    <Grid.Row>
                        <Message>
                            <Message.Header>
                                <h1>Hello!</h1>
                                <Divider />
                                <p><strong>Thank you so much for agreeing to participate in our study!</strong></p>
                            </Message.Header>
                            <p>
                                Our goal is to understand how humans discover patterns in data.
                            </p>
                        </Message>
                    </Grid.Row>
                    <Divider />
                    <Grid.Row>
                        <Message>
                            <Message.Header>
                                <h2>Your Role</h2>
                            </Message.Header>
                            <Divider />
                            <p>
                                In this study, you should find patterns that most reasonably hold over a large dataset
                                by observing only <strong>a small sample of the dataset.</strong> You will inspect this
                                small sample interactively. You will perform this task for five different datasets.
                            </p>                     
                        </Message>
                    </Grid.Row>
                    <Divider />
                    <Grid.Row>
                        <Message>
                            <Message.Header>
                                <h3>Enter your email address to get started!</h3>
                            </Message.Header>
                            <Divider />
                            <Form>
                                <Form.Field>
                                    <Input
                                        type='email'
                                        size='large'
                                        label='Email Address: '
                                        placeholder='Enter your email address'
                                        onChange={(_e, props) => setEmail(props.value)}
                                    />
                                </Form.Field>
                                <Button
                                    positive
                                    size='big'
                                    type='submit'
                                    disabled={email === '' || !email.includes('@')}
                                    onClick={handleGetStarted}
                                >
                                    Get Started
                                </Button>
                            </Form>
                        </Message>
                        
                    </Grid.Row>
                </Grid.Column>
            </Grid>
            <Dimmer active={processing}>
                <Loader active={processing} size='big'>
                    Loading
                </Loader>
            </Dimmer>
        </Dimmer.Dimmable>
    )
}