import { AxiosResponse } from 'axios'
import React, { FC, useEffect, useState } from 'react'
import { useHistory, useLocation } from 'react-router-dom'
import {
    Button,
    Loader,
    Container,
    Grid,
    Dimmer,
    Segment,
    Message,
    Divider,
    Input,
    Checkbox,
    Dropdown
} from 'semantic-ui-react'
import server from '../utils/server'
import logo from '../images/OSU_horizontal_2C_O_over_B.png'

interface PostInteractionProps {}

export const PostInteraction: FC<PostInteractionProps> = () => {

    const history = useHistory()
    const location = useLocation()
    const { header, email, scenarios } = location.state as any

    const [processing, setProcessing] = useState<boolean>(false) // The visibility of the processing indicator
    const [fd, setFD] = useState<{[key: string]: string}>({}) // The user's initial FD hypothesis for the next interaction
    const [doesntKnowFD, setDoesntKnowFD] = useState<boolean>(false) // Whether or not the user has an idea of the initial FD
    const [fdComment, setFDComment] = useState<string>('') // Any comment the user provides with their initial FD hypothesis
    const [dataOverviewRead, setDataOverviewRead] = useState<boolean>(false) // Whether or not the user read the data overview for this interaction
    const [done, setDone] = useState<boolean>(false) // Whether or not the user has completed all of their interactions
    const [comments, setComments] = useState<string>('')

    /** Initialize the initial FD object */
    useEffect(() => {
        const init_fd: {[key: string]: string} = {}
        header.forEach((h: string) => init_fd[h] = 'N/A')
        setFD(init_fd)
    }, [header])

    /** Define the details of each scenario */
    const scenarioDetails: {[key: number]: {[key: string]: string | null }} = {
        15: {
            domain: 'Movie',
            info: `
            This dataset describes information about various English-language movies and TV shows,
            such as the title of the movie or TV show, the type of program it is (e.g. movie or TV episode), and
            its MPAA or FCC rating (e.g. PG-13, R, TV-14).
            `,
            note: null
        },
        8: {
            domain: 'Airport',
            info: `
            This dataset describes information about various airports and airfields, including the name of
            the airfield, the type of airfield it is (airport, heliport, or seaplane base), and the person,
            group, or entity managing the airfield.
            `,
            note: 'Some airfields have no manager, and these are listed with a manager value of "NO MANAGER."'
        },
        14: {
            domain: 'Movie',
            info: `
            This dataset describes information about various English-language movies and TV shows,
            including the title of the movie of TV show, the genre of the program, the type of program
            it is (e.g. movie or TV episode), and what year the program was released in.
            `,
            note: null
        },
        11: {
            domain: 'Airport',
            info: `
            This dataset describes information about various airports and airfields, including the name of
            the airfield, the person, group, or entity that owns the airfield, and the person, group, or
            entity that owns the airfield.
            `,
            note: 'Some airfields have no manager, and these are listed with a manager value of "NO MANAGER."'
        },
        13: {
            domain: 'Airport',
            info: `
            This dataset describes information about various airports and airfields, including the name of
            the airfield, the person, group, or entity that owns the airfield, and the person, group, or
            entity that owns the airfield.
            `,
            note: 'Some airfields have no manager, and these are listed with a manager value of "NO MANAGER."'
        }
    }

    /**
     * Handle the user indicating they're ready to begin the next interaction (pressing the Go to the Data button)
     */
    const handleReady = async () => {
        setProcessing(true) // turn on the processing indicator
        const next_scenario: number = scenarios.splice(0, 1) as number

        // build the user's FD hypothesis as a string
        const lhs: string[] = Object.keys(fd).filter((k: string) => fd[k] === 'LHS')
        lhs.sort()
        const rhs: string[] = Object.keys(fd).filter((k: string) => fd[k] === 'RHS')
        rhs.sort()
        const initial_fd: string = `(${lhs.join(', ')}) => ${rhs.join(', ')}`
        
        // send the user's hypothesis to the backend and begin the next interaction
        const response: AxiosResponse = await server.post('/import', {
            email,
            scenario_id: next_scenario.toString(),
            initial_fd: doesntKnowFD ? 'Not Sure' : initial_fd,
            fd_comment: fdComment,
        })
        const { project_id, description } = response.data
        
        // Go to the interaction page for the next interaction
        history.push('/interact', {
            email,
            scenarios,
            scenario_id: next_scenario.toString(),
            header,
            project_id,
            description
        })
    }

    /** Handle the user submitting their comments when they've completed all scenarios */
    const handleDoneComments = async (mode: 'skip' | 'submit') => {
        setProcessing(true)
        // Send the user's final comments to the backend
        const response: AxiosResponse = await server.post('/done', {
            email,
            comments: mode === 'submit' ? comments : '',
        })
        if (response.status === 201) {
            setProcessing(false)
            setDone(true)
        }
    }

    /** Test that the user's FD is valid */
    const isValidFD = () => {
        // There must be at least one attribute on both the LHS and RHS
        return Object.keys(fd).filter((k: string) => fd[k] === 'LHS').length !== 0
        && Object.keys(fd).filter((k: string) => fd[k] === 'RHS').length !== 0
    }

    /** Build the user's FD hypothesis */
    const buildFD = (attrs: any, side: 'LHS' | 'RHS') => {
        if (attrs) {
            const fresh_fd: {[key: string]: string} = {}
            header.forEach((h: string) => {
                fresh_fd[h] = fd[h]
            }) // Start with the user's previous hypothesis
            attrs.forEach((attr: string) => {
                fresh_fd[attr] = side
            }) // Update the LHS/RHS distinctions for the updated attributes
            header.forEach((h: string) => {
                if (!attrs.includes(h) && fresh_fd[h] === side) fresh_fd[h] = 'N/A'
            }) // Mark removed attributes as N/A
            setFD(fresh_fd)
        }
    }

    return (
        <Dimmer.Dimmable as={Segment} dimmed={processing}>
            <Grid centered stretched={false} columns={1} className='site-page home'>
                <Grid.Column>
                    <Grid.Row>
                        <Container className='section' style={{ backgroundColor: 'white', position: 'absolute', top: 0, right: 0, width: '10vw', maxWidth: '500px', height: '8vh', borderBottomLeftRadius: 20 }} >
                            <img src={logo} style={{ padding: 10, position: 'absolute', top: 0, right: 0, width: '100%', height: 'auto' }} alt='OSU logo' />
                        </Container>
                        <Container className='content-centered home-header box-blur'>
                            <span className='home-title'>Discovering Patterns in Data</span>
                        </Container>
                        <Message success>
                            <Message.Header>
                                <h1>Scenario Complete</h1>
                            </Message.Header>
                            <p>
                                {
                                    scenarios.length > 0
                                    ? `You completed a scenario! Let's take a look at your next dataset now.`
                                    : `You completed your last scenario!`
                                }
                            </p>
                        </Message>
                    </Grid.Row>
                    <Divider />
                    <Grid.Row>
                    {
                        scenarios.length > 0 ? (
                            <Message>
                                <Message.Header>
                                    <h2>Your Next Dataset</h2>
                                </Message.Header>
                                <Divider />
                                <h3>{`${scenarioDetails[scenarios[0]].domain} Data`}</h3>
                                <p>
                                    {scenarioDetails[scenarios[0]].info}
                                </p>
                                {
                                    scenarioDetails[scenarios[0]].note && (
                                        <p>
                                            <strong>NOTE: </strong>{scenarioDetails[scenarios[0]].note}
                                        </p>
                                    )
                                }
                                <Divider />
                                <Message>
                                    <Message.Header>
                                        <h3>
                                        This dataset has the following attributes: [{header.join(', ')}]. Without looking at the data, what FD do you think holds with the full {scenarioDetails[scenarios[0]].domain} dataset?
                                        </h3>
                                        <p>Indicate your answer using the dropdowns below. Pick one or more attributes for each side of the FD.</p>
                                    </Message.Header>
                                    <Divider />
                                    <div style={{ flexDirection: 'row' }}>
                                    <Dropdown
                                        placeholder='Select an attribute(s)...'
                                        multiple
                                        selection
                                        options={header.filter((h: string) => fd[h] !== 'RHS').map((h: string) => ({ key: h, text: h, value: h }))}
                                        onChange={(_e, props) => buildFD(props.value, 'LHS')}
                                    />
                                    <span style={{ paddingLeft: 10, paddingRight: 10, fontSize: 20 }}><strong>{'=>'}</strong></span>
                                    <Dropdown
                                        placeholder='Select an attribute(s)...'
                                        multiple
                                        selection
                                        options={header.filter((h: string) => fd[h] !== 'LHS').map((h: string) => ({ key: h, text: h, value: h }))}
                                        onChange={(_e, props) => buildFD(props.value, 'RHS')}
                                    />
                                    </div>
                                    {
                                        !isValidFD() && !doesntKnowFD && (
                                            <Message error>
                                                You must either select at least one attribute for the LHS and one for the RHS, or check "I Don't Know."
                                            </Message>
                                        )
                                    }
                                    <h3 style={{ paddingTop: 10, paddingBottom: 10 }}>OR</h3>
                                    <Checkbox
                                        label={`I Don't Know`}
                                        name='idk_checkbox'
                                        value='IDK'
                                        checked={doesntKnowFD}
                                        onChange={() => setDoesntKnowFD(!doesntKnowFD)}
                                    />
                                    <Divider style={{ paddingBottom: 10, paddingTop: 10 }} />
                                    <Input
                                        fluid
                                        type='text'
                                        size='large'
                                        placeholder='Add any comments supporting your thinking here...'
                                        onChange={(_e, props) => setFDComment(props.value)}
                                    />
                                </Message>
                                {
                                    dataOverviewRead ? (
                                        <Message color='green'><p>Scroll Down</p></Message>
                                    ) : (
                                        <Button positive size='big' onClick={() => setDataOverviewRead(true)} disabled={!doesntKnowFD && !isValidFD()}>Continue</Button>
                                    )
                                }
                                {
                                    dataOverviewRead && (
                                        <>
                                            <Divider />
                                            <Message info>
                                                <Message.Header>
                                                    When you're ready to begin interacting with your next dataset, click "Go to the Data" below.
                                                </Message.Header>
                                            </Message>
                                            <Button positive size='big' onClick={handleReady}>Go to the Data</Button>
                                        </>
                                    )
                                }
                            </Message>
                        ) : (
                            <Message success>
                                {
                                    done ? (
                                        <>
                                            <Message.Header>
                                                Thanks for participating in our study!
                                            </Message.Header>
                                        </>
                                    ) : (
                                        <>
                                            <Message.Header>
                                                You're all done! How did everything go? Leave any comments or feedback you have about your study experience below!
                                            </Message.Header>
                                            <Input
                                                fluid
                                                type='text'
                                                size='large'
                                                placeholder='Add any comments or feedback here...'
                                                onChange={(_e, props) => setComments(props.value)}
                                                style={{ paddingTop: 20, paddingBottom: 20}}
                                            />
                                            <div style={{ flexDirection: 'row' }}>
                                                <Button color='grey' size='big' onClick={() => handleDoneComments('skip')} style={{ marginRight: 10 }}>Skip</Button>
                                                <Button positive size='big' onClick={() => handleDoneComments('submit')}>Submit</Button>
                                            </div>
                                        </>
                                    )
                                }
                            </Message>
                        )
                    }
                    </Grid.Row>
                    <Grid.Row>
                        
                    </Grid.Row>
                            {/* </>
                        )
                    } */}
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