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
    Table,
    Form,
    Radio,
    Input,
    Checkbox,
    Dropdown
} from 'semantic-ui-react'
import server from '../utils/server'
import logo from '../images/OSU_horizontal_2C_O_over_B.png'

interface StartProps {}

export const Start: FC<StartProps> = () => {

    const history = useHistory()
    const location = useLocation()
    const { email, scenarios, status } = location.state as any

    const [processing, setProcessing] = useState<boolean>(false) // The visibility of the processing indicator
    const [interfaceGuideRead, setInterfaceGuideRead] = useState<boolean>(false) // Whether or not the interface guide has been read
    const [dataOverviewRead, setDataOverviewRead] = useState<boolean>(false) // Whether or not the data overview has been read
    const [fdReviewRead, setFDReviewRead] = useState<boolean>(false) // Whether or not the FD review has been read
    const [quizQ1Done, setQuizQ1Done] = useState<boolean>(false) // Whether or not the user has completed Question 1 of the knowledge check
    const [quizFullDone, setQuizFullDone] = useState<boolean>(false) // Whether or not the user has completed the knowledge check
    const [quizAnswersReviewed, setQuizAnswersReviewed] = useState<boolean>(false) // Whether or not the user answered all questions in the knowledge check
    const [header, setHeader] = useState<string[]>([]) // The schema for the user's first interaction
    const [fd, setFD] = useState<{[key: string]: string}>({}) // The user's initial FD hypothesis
    const [doesntKnowFD, setDoesntKnowFD] = useState<boolean>(false) // Whether or not the user has any idea about the initial FD
    const [fdComment, setFDComment] = useState<string>('') // Any comment the user has left about their initial FD hypothesis

    /** Define the user's responses to the knowledge check questions, as well as the correct answers to those questions */
    const [q1Response, setQ1Response] = useState<string>('')
    const q1CorrectAnswer = 'name'
    const [q2Response, setQ2Response] = useState<string>('')
    const q2CorrectAnswers = ['4_305', '6_305', '4_FL', '6_CA']

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

    /** Initialize the FD map for this schema */
    useEffect(() => {
        const init_fd: {[key: string]: string} = {}
        header.forEach((h: string) => init_fd[h] = 'N/A')
        setFD(init_fd)
    }, [header])

    /** The user is resuming their work in a scenario; get the schema for that dataset */
    useEffect(() => {
        if (status === 'resume') {
            const first_scenario: number = scenarios[0] as number
            server.post('/resume', {
                email,
                scenario_id: first_scenario.toString(),
            }).then((response) => {
                setHeader(response.data.header)
            }).catch((err) => console.error(err))
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    /** Submit the user's knowledge check responses */
    const handleQuizDone = async () => {
        setProcessing(true)
        const answers = [
            {
                answer: q1Response,
                correctAnswer: q1CorrectAnswer,
                correct: q1Response === q1CorrectAnswer
            },
            {
                answer: q2Response,
                correctAnswer: q2CorrectAnswers,
                correct: q2CorrectAnswers.includes(q2Response)
            }
        ]
        const first_scenario: number = scenarios[0] as number
        const response: AxiosResponse = await server.post('/pre-survey', {
            email,
            scenario_id: first_scenario.toString(),
            answers
        }) // Send answers to the backend and get the schema for this scenario
        setQuizFullDone(true)
        setHeader(response.data.header)
        setProcessing(false)
    }

    /** Handle the user indicating they're ready to begin the first interaction */
    const handleReady = async () => {
        setProcessing(true) // show the processing indicator
        const first_scenario: number = scenarios.splice(0, 1) as number

        // Build the user's initial FD guess
        const lhs: string[] = Object.keys(fd).filter((k: string) => fd[k] === 'LHS') // Get the LHS
        lhs.sort()
        const rhs: string[] = Object.keys(fd).filter((k: string) => fd[k] === 'RHS') // Get the RHS
        rhs.sort()
        const initial_fd: string = `(${lhs.join(', ')}) => ${rhs.join(', ')}` // Build the FD
        console.log(initial_fd)
        const response: AxiosResponse = await server.post('/import', {
            email,
            scenario_id: first_scenario.toString(),
            initial_fd: doesntKnowFD ? 'Not Sure' : initial_fd,
            fd_comment: fdComment,
        }) // Send the user's initial FD guess to the backend
        const { project_id, description } = response.data
        history.push('/interact', {
            email,
            scenarios,
            scenario_id: first_scenario.toString(),
            header,
            project_id,
            description
        }) // Go the interaction page
        setProcessing(false)
    }

    // Check if the user has built a valid functional dependency
    const isValidFD = () => {
        // The FD must have at least one attribute on the LHS and at least on the RHS
        return Object.keys(fd).filter((k: string) => fd[k] === 'LHS').length > 0
        && Object.keys(fd).filter((k: string) => fd[k] === 'RHS').length > 0
    }

    /** Build or update the user's hypothesized FD */
    const buildFD = (attrs: any, side: 'LHS' | 'RHS') => {
        if (attrs) {
            const fresh_fd: {[key: string]: string} = {}
            header.forEach((h: string) => {
                fresh_fd[h] = fd[h]
            }) // Get the current FD
            attrs.forEach((attr: string) => {
                fresh_fd[attr] = side
            }) // Update the FD for the provided attributes
            header.forEach((h: string) => {
                if (!attrs.includes(h) && fresh_fd[h] === side) fresh_fd[h] = 'N/A'
            }) // If an attribute has been removed from the user's hypothesis, set it's side value to N/A (i.e. not LHS or RHS)
            console.log(fresh_fd)
            setFD(fresh_fd)
        }
    }

    /** Data to show in example table */
    const fdExampleData = [
        {
            id: 1,
            address: '123 SW Elm St',
            city: 'Portland',
            state: 'OR',
            zip: 97123,
        },
        {
            id: 2,
            address: '777 Broadway',
            city: 'Seattle',
            state: 'WA',
            zip: 98108,
        },
        {
            id: 3,
            address: '800 SW 6th Ave',
            city: 'Portland',
            state: 'OR',
            zip: 97209,
        },
        {
            id: 4,
            address: '250 NE Irving St',
            city: 'Los Angeles',
            state: 'CA',
            zip: 90254,
        },
        {
            id: 5,
            address: '515 NW Marshall St',
            city: 'Portland',
            state: 'OR',
            zip: 97123,
        },
        {
            id: 6,
            address: '800 SW 6th Ave',
            city: 'Portland',
            state: 'ME',
            zip: 97209,
        }
    ]

    /** Table data for Question 1 */
    const q1Data = [
        {
            name: 'Michael',
            areacode: 503,
            state: 'OR',
            zip: 97007
        },
        {
            name: 'Nate',
            areacode: 206,
            state: 'WA',
            zip: 98802
        },
        {
            name: 'Leilani',
            areacode: 808,
            state: 'HI',
            zip: 96850
        },
        {
            name: 'Tobias',
            areacode: 541,
            state: 'OR',
            zip: 97401
        },
        {
            name: 'Samantha',
            areacode: 206,
            state: 'WA',
            zip: 43153
        },
        {
            name: 'Tobias',
            areacode: 541,
            state: 'OR',
            zip: 97401
        },
    ]

    /** Table data for question 2 */
    const q2Data = [
        {
            id: 1,
            name: 'Darrell',
            areacode: 775,
            state: 'NV',
            zip: 89501
        },
        {
            id: 2,
            name: 'Henry',
            areacode: 404,
            state: 'GA',
            zip: 30334
        },
        {
            id: 3,
            name: 'Blake',
            areacode: 775,
            state: 'NV',
            zip: 89501
        },
        {
            id: 4,
            name: 'Jusuf',
            areacode: 305,
            state: 'FL',
            zip: 33130
        },
        {
            id: 5,
            name: 'Shania',
            areacode: 775,
            state: 'NV',
            zip: 89501
        },
        {
            id: 6,
            name: 'Ellen',
            areacode: 305,
            state: 'CA',
            zip: 33128
        },
    ]

    return (
        <Dimmer.Dimmable as={Segment} dimmed={processing}>
            <Grid centered stretched={false} columns={1} className='site-page home'>
                <Grid.Column>
                    <Divider />
                    <Grid.Row className='content-centered'>
                        <Container className='section' style={{ backgroundColor: 'white', position: 'absolute', top: 0, right: 0, width: '10vw', maxWidth: '500px', height: '8vh', borderBottomLeftRadius: 20 }} >
                            <img src={logo} style={{ padding: 10, position: 'absolute', top: 0, right: 0, width: '100%', height: 'auto' }} alt='OSU logo' />
                        </Container> 
                        <Container className='home-header box-blur'>
                            <span className='home-title'>Discovering Patterns in Data</span>
                        </Container>
                    </Grid.Row>
                    {
                        status === 'begin' && (
                            <>
                                <Grid.Row>
                                    <Message>
                                        <Message.Header>
                                            <h2>Let's Review Functional Dependencies</h2>
                                        </Message.Header>
                                        <Divider />
                                        <Message info>
                                            <Message.Header>
                                                <h3>What is an FD?</h3>
                                            </Message.Header>
                                            <p>
                                                A <strong>functional dependency</strong>, or <strong>FD</strong>, is a pattern that explains
                                                how some attributes determine some other attributes in a dataset.
                                            </p>
                                        </Message>
                                        <p>
                                            For example, in the dataset below, an address's city and zip code determine its state.
                                            This pattern is represented by the expression <strong>{'(city, zip) => state'}</strong>.
                                        </p>
                                        <Table>
                                            <Table.Header>
                                                <Table.Row>
                                                {
                                                    Object.keys(fdExampleData[0]).map((h: string) => h !== 'id' && (
                                                        <Table.HeaderCell key={h}>{h}</Table.HeaderCell>
                                                    ))
                                                }
                                                </Table.Row>
                                            </Table.Header>
                                            <Table.Body>
                                                {
                                                    fdExampleData.map((e) => e.id !== 6 && (
                                                        <Table.Row>
                                                            {
                                                                Object.entries(e).map(([k, v], i) => k !== 'id' && (
                                                                    <Table.Cell key={i}>{v}</Table.Cell>
                                                                ))
                                                            }
                                                        </Table.Row>
                                                    ))
                                                }
                                            </Table.Body>
                                        </Table>
                                        <Message warning>
                                            <Message.Header>
                                                <h4>There may be one or more attributes on the left or right-hand sides of an FD (on the left or right side of the "{'=>'}").</h4>
                                            </Message.Header>
                                            <p>
                                                For example, address and city determine zip code and state. This is written
                                                as <strong>{'(address, city) => (zip, state)'}</strong>.
                                            </p>
                                        </Message>
                                        {/* <Message warning>
                                            <Message.Header>
                                                <h4>
                                                    The attributes that functionally determine other attributes are collectively called the left-hand side (LHS) of the rule,
                                                    while the attributes that are dependent on the left-hand side are collectively called the right-hand side (RHS) of the rule.
                                                </h4>
                                            </Message.Header>
                                            <p>
                                                E.g. in the rule <strong>{'(city, zip) => state'}</strong>, city and zip collectively form the LHS and state forms the RHS.
                                                In the rule <strong>{'(id) => address, city, state, zip'}</strong>, id forms the LHS and address, city, state, and zip collectively form the RHS.
                                            </p>
                                        </Message> */}
                                        <p>
                                            For more information on FDs and to see more examples, you can go <a href='https://en.wikipedia.org/wiki/Functional_dependency#Examples' target='_blank' rel='noopener noreferrer'>here</a>.
                                        </p>
                                        <Divider />
                                        <Message info>
                                            <Message.Header>
                                                <h3>What is an exception to an FD?</h3>
                                            </Message.Header>
                                            <p>
                                                If a cell in a tuple has a value that does not align with the rest of the dataset with
                                                respect to an FD, the cell is said to be an <strong>exception</strong> to the FD.
                                            </p>
                                        </Message>
                                        <p>
                                            In the following dataset, the two tuples with the address "800 6th Ave" have exceptions to the FD <strong>{'(city, zip) => state'}</strong> as
                                            two places with the same city and ZIP code have different states listed. Cells relevant to this exception have been highlighted below.
                                        </p>
                                        <Table>
                                            <Table.Header>
                                                <Table.Row>
                                                {
                                                    Object.keys(fdExampleData[0]).map((h: string) => h !== 'id' && (
                                                        <Table.HeaderCell key={h}>{h}</Table.HeaderCell>
                                                    ))
                                                }
                                                </Table.Row>
                                            </Table.Header>
                                            <Table.Body>
                                                {
                                                    fdExampleData.map((e) => e.id !== 1 && (
                                                        <Table.Row>
                                                            {
                                                                Object.entries(e).map(([k, v], _i) => k !== 'id' && (
                                                                    (e.id === 3 || e.id === 6) && (k === 'city' || k === 'zip' || k === 'state') ? (
                                                                        <Table.Cell style={{ backgroundColor: '#FFF3CD' }}>
                                                                            {v}
                                                                        </Table.Cell>
                                                                    ) : (
                                                                        <Table.Cell>{v}</Table.Cell>
                                                                    )
                                                                ))
                                                            }
                                                        </Table.Row>
                                                    ))
                                                }
                                            </Table.Body>
                                        </Table>
                                        {
                                            fdReviewRead ? (
                                                <Message color='green'><p>Scroll Down</p></Message>
                                            ) : (
                                                <Button positive size='big' onClick={() => setFDReviewRead(true)}>Continue</Button>
                                            )
                                        }
                                    </Message>
                                </Grid.Row>
                                {
                                    fdReviewRead && (
                                        <>
                                            <Divider />
                                            <Grid.Row>
                                                <Message>
                                                    <Message.Header>
                                                        <h2>Quiz</h2>
                                                        <Divider />
                                                        <h4>This serves to evaluate your understanding of FDs and their exceptions. It's just two questions.</h4>
                                                    </Message.Header>
                                                    <Divider />
                                                    <p><strong>1)</strong> The following table contains information about employees at a company. Which of the following FDs holds with fewest exceptions over this dataset?</p>
                                                    {
                                                        quizQ1Done && (
                                                            <Message positive={q1Response === q1CorrectAnswer} negative={q1Response !== q1CorrectAnswer}>
                                                                <Message.Header>
                                                                    {
                                                                        q1Response === q1CorrectAnswer
                                                                        ? 'Correct!'
                                                                        : 'Incorrect'
                                                                    }
                                                                </Message.Header>
                                                                {
                                                                    q1Response !== q1CorrectAnswer && (
                                                                        'The correct answer has been highlighted with a green box.'
                                                                    )
                                                                }
                                                            </Message>
                                                        )
                                                    }
                                                    <Table>
                                                        <Table.Header>
                                                            <Table.Row>
                                                            {
                                                                Object.keys(q1Data[0]).map((h: string) => (
                                                                    <Table.HeaderCell key={h}>{h}</Table.HeaderCell>
                                                                ))
                                                            }
                                                            </Table.Row>
                                                        </Table.Header>
                                                        <Table.Body>
                                                            {
                                                                q1Data.map((e) => {
                                                                    return (
                                                                        <Table.Row>
                                                                            {
                                                                                Object.values(e).map((v) => (
                                                                                    <Table.Cell>{v}</Table.Cell>
                                                                                ))
                                                                            }
                                                                        </Table.Row>
                                                                    )
                                                                })
                                                            }
                                                        </Table.Body>
                                                    </Table>
                                                    <Form>
                                                        <Form.Field>
                                                            <Radio
                                                                label='areacode determines all other attributes'
                                                                name='q1RadioGroup'
                                                                value='areacode'
                                                                checked={q1Response === 'areacode'}
                                                                onChange={() => !quizQ1Done && setQ1Response('areacode')}
                                                            />
                                                        </Form.Field>
                                                        <Form.Field>
                                                            {
                                                                quizQ1Done ? (
                                                                    <Radio
                                                                        style={{ border: '2px solid green', padding: 10 }}
                                                                        label='name determines all other attributes'
                                                                        name='q1RadioGroup'
                                                                        value='name'
                                                                        checked={q1Response === 'name'}
                                                                        onChange={() => !quizFullDone && setQ1Response('name')}
                                                                    />
                                                                ) : (
                                                                    <Radio
                                                                        label='name determines all other attributes'
                                                                        name='q1RadioGroup'
                                                                        value='name'
                                                                        checked={q1Response === 'name'}
                                                                        onChange={() => !quizFullDone && setQ1Response('name')}
                                                                    />
                                                                )
                                                            }
                                                        </Form.Field>
                                                        <Form.Field>
                                                            <Radio
                                                                label='areacode and state determine all other attributes'
                                                                name='q1RadioGroup'
                                                                value='combo'
                                                                checked={q1Response === 'combo'}
                                                                onChange={() => !quizFullDone && setQ1Response('combo')}
                                                            />
                                                        </Form.Field>
                                                        <Form.Field>
                                                            <Radio
                                                                label='zip determines all other attributes'
                                                                name='q1RadioGroup'
                                                                value='zip'
                                                                checked={q1Response === 'zip'}
                                                                onChange={() => setQ1Response('zip')}
                                                            />
                                                        </Form.Field>
                                                    </Form>
                                                    <Divider />
                                                    {
                                                        quizQ1Done ? (
                                                            <Message color='green'><p>Scroll Down</p></Message>
                                                        ) : (
                                                            <Button positive size='big' disabled={q1Response === ''} onClick={() => setQuizQ1Done(true)}>Next</Button>
                                                        )
                                                    }
                                                    { 
                                                        quizQ1Done && (
                                                            <>
                                                                <Divider />
                                                                <p><strong>2)</strong> The following table contains information about employees at a company. It contains exceptions to the FD <strong>{'areacode => state'}.</strong> Find and mark one exception to this FD.</p>
                                                                {
                                                                    quizFullDone && (
                                                                        <Message positive={q2CorrectAnswers.includes(q2Response)} negative={!q2CorrectAnswers.includes(q2Response)}>
                                                                            <Message.Header>
                                                                                {
                                                                                    q2CorrectAnswers.includes(q2Response)
                                                                                    ? 'Correct!'
                                                                                    : 'Incorrect'
                                                                                }
                                                                            </Message.Header>
                                                                            All possible correct answers have been highlighted in green.
                                                                        </Message>
                                                                    )
                                                                }
                                                                <Table>
                                                                    <Table.Header>
                                                                        <Table.Row>
                                                                        {
                                                                            Object.keys(q2Data[0]).map((h: string) => h !== 'id' && (
                                                                                <Table.HeaderCell key={h}>{h}</Table.HeaderCell>
                                                                            ))
                                                                        }
                                                                        </Table.Row>
                                                                    </Table.Header>
                                                                    <Table.Body>
                                                                        {
                                                                            q2Data.map((e) => {
                                                                                return (
                                                                                    <Table.Row>
                                                                                        {
                                                                                            Object.entries(e).filter(([k, v], i) => k !== 'id').map(([k, v], i) => {
                                                                                                if (quizFullDone && q2CorrectAnswers.includes(`${e.id}_${v}`)) {
                                                                                                    return (
                                                                                                        <Table.Cell
                                                                                                            key={`${e.id}_${v}`}
                                                                                                            style={{backgroundColor: '#E5F9E6' }}
                                                                                                        >
                                                                                                        {v}
                                                                                                        </Table.Cell>
                                                                                                    )
                                                                                                } else {
                                                                                                    return q2Response === `${e.id}_${v}`
                                                                                                    ? (
                                                                                                        <Table.Cell
                                                                                                            key={`${e.id}_${v}`}
                                                                                                            style={{ cursor: 'pointer', backgroundColor: '#FFF3CD' }}
                                                                                                            onClick={() => {
                                                                                                                if (!quizFullDone) {
                                                                                                                    setQ2Response('')
                                                                                                                }
                                                                                                            }}
                                                                                                        >
                                                                                                        {v}
                                                                                                        </Table.Cell>
                                                                                                    ) : (
                                                                                                        <Table.Cell
                                                                                                            key={`${e.id}_${v}`}
                                                                                                            style={{ cursor: 'pointer' }}
                                                                                                            onClick={() => {
                                                                                                                if (!quizFullDone) {
                                                                                                                    setQ2Response(`${e.id}_${v}`)
                                                                                                                }
                                                                                                            }}
                                                                                                        >
                                                                                                        {v}
                                                                                                        </Table.Cell>
                                                                                                    )
                                                                                                }
                                                                                            })
                                                                                        }
                                                                                    </Table.Row>
                                                                                )
                                                                            })
                                                                        }
                                                                    </Table.Body>
                                                                </Table>
                                                                {
                                                                    quizFullDone ? (
                                                                        quizAnswersReviewed ? (
                                                                            <Message color='green'><p>Scroll Down</p></Message>
                                                                        ) : (
                                                                            <>
                                                                                <Message warning><p>Review Your Answers</p></Message>
                                                                                <Button positive size='big' onClick={() => setQuizAnswersReviewed(true)}>Continue</Button>
                                                                            </>
                                                                        )
                                                                    ) : (
                                                                        <Button positive size='big' disabled={q1Response === '' || q2Response === ''} onClick={handleQuizDone}>Submit</Button>
                                                                    )
                                                                }
                                                            </>
                                                        )
                                                    }
                                                    
                                                </Message>
                                            </Grid.Row>
                                        </>
                                    )
                                }
                                {
                                    quizFullDone && quizAnswersReviewed && (
                                        <>
                                            <Divider />
                                            <Grid.Row>
                                                <Message>
                                                    <Message.Header>
                                                        <h2>How to Interact With the Datasets</h2>
                                                    </Message.Header>
                                                    <Divider />
                                                    <p>
                                                        You will find FDs in five different datasets interactively. For each dataset, you'll
                                                        be shown small samples of the dataset in some rounds. You will never be shown the
                                                        entire dataset. Your job is to suggest an FD you think holds with the fewest exceptions
                                                        <strong>over the entire dataset</strong> given everything you've seen so far. The FDs
                                                        that you find over the observed samples <strong>should generalize reasonably
                                                        accurately</strong> to the entire dataset.
                                                    </p>
                                                    <p>
                                                        For each dataset, you will be shown 8-12 tuples from the full dataset in each round. You
                                                        may revise your suggested FD in each round given everything you've seen so far. You will
                                                        enter this FD using the dropdown selectors below the sample and mark any exceptions to this
                                                        FD in the sample in each round. After you're done in each round, click the
                                                        green <strong><i>Next</i></strong> button to go to the next round. To mark a cell as an
                                                        exception to an FD, click on the cell. The cell will be highlighted yellow. You can undo
                                                        your decision for that cell by simply clicking on the cell again to unhighlight and unmark
                                                        it. If you don't see anything that should be marked, you don't have to mark anything. Just
                                                        answer the prompt using the dropdowns and click <strong><i>Next</i></strong> to get a fresh sample.
                                                    </p>
                                                    <p>
                                                        Your markings will be visible throughout the entire interaction, i.e. if you previously marked
                                                        a cell as an exception and that tuple reappears in a sample later on, the cell will still be
                                                        highlighted so that you can review and change your previous markings alongside new data.
                                                    </p>
                                                    <p>
                                                        After 8 rounds, if you're sure that your suggested FD holds over the entire dataset with the
                                                        fewest exceptions, you can click <strong><i>I'm All Done</i></strong> to finish working with
                                                        the dataset. You may continue the interaction up to a total of 15 rounds before moving on
                                                        to the next dataset.
                                                    </p>
                                                    {
                                                        interfaceGuideRead ? (
                                                            <Message color='green'><p>Scroll Down</p></Message>
                                                        ) : (
                                                            <Button positive size='big' onClick={() => setInterfaceGuideRead(true)}>Continue</Button>
                                                        )
                                                    }
                                                </Message>
                                            </Grid.Row>
                                        </>
                                    )
                                }
                            </>
                        )
                    }
                    
                    {
                        (interfaceGuideRead || status === 'resume') && (
                            <>
                                <Divider />
                                <Grid.Row>
                                    <Message>
                                        <Message.Header>
                                            <h2>Your {status === 'begin' ? 'First' : 'Next'} Dataset</h2>
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
                                                style={{ paddingBottom: 10 }}
                                            />
                                            <Divider />
                                            <Input
                                                fluid
                                                style={{ paddingTop: 10 }}
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
                                                            When you're ready to begin interacting with the dataset, click "Go to the Data" below.
                                                        </Message.Header>
                                                    </Message>
                                                    <Button positive size='big' onClick={handleReady}>Go to the Data</Button>
                                                </>
                                            )
                                        }
                                    </Message>
                                </Grid.Row>
                            </>
                        )
                    }
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