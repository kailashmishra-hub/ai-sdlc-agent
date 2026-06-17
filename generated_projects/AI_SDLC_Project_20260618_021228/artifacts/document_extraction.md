## Sources

- Functional Requirements Document.pdf

## Extracted Content

Functional Requirements Document (FRD)
Project Name
Hotel Booking Management System
Module Name
Booking Management
Version
1.0
Purpose
The Hotel Booking Management System provides API services that allow consumers to create hotel
bookings and retrieve booking information using a unique Booking Identifier .
The system exposes REST APIs for booking creation and booking retrieval.
1. Scope
The scope of this document includes:
Create Booking
Retrieve Booking Details
Booking Validation
Booking Identifier Generation
Booking Information Retrieval
The document serves as input for:
Business Analysts
Developers
QA Teams
API Consumers
AI SDLC Platform
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
1
2. System Overview
The Booking Service allows users to:
Create a new hotel booking.
Receive a unique Booking Identifier .
Retrieve booking details using the Booking Identifier .
3. API Catalog
API Name Method Endpoint
Create BookingPOST /booking
Retrieve BookingGET /booking/{bookingid}
4. Create Booking Service
Service Name
Create Booking
Endpoint
POST https://restful-booker .herokuapp.com/booking
Description
The Create Booking API allows consumers to create a hotel booking by providing guest information and
reservation details.
Request Payload
{
"firstname": "Kailash",
"lastname": "Mishra",
"totalprice": 1500,
"depositpaid": true,
"bookingdates": {
"checkin": "2025-12-25",
"checkout": "2025-12-30"
},
1. 
2. 
3. 
2
"additionalneeds": "Breakfast"
}
Input Parameters
Field Name Data TypeMandatory
firstname String Yes
lastname String Yes
totalprice Number Yes
depositpaid Boolean Yes
bookingdates.checkinDate Yes
bookingdates.checkoutDate Yes
additionalneeds String No
Functional Requirements
FR-CB-001
The system shall expose a Create Booking API.
FR-CB-002
The API shall accept booking details in JSON format.
FR-CB-003
The system shall accept First Name.
FR-CB-004
The system shall accept Last Name.
FR-CB-005
The system shall accept Total Price.
FR-CB-006
The system shall accept Deposit Paid status.
3
FR-CB-007
The system shall accept Check-In Date.
FR-CB-008
The system shall accept Check-Out Date.
FR-CB-009
The system shall optionally accept Additional Needs.
FR-CB-010
The system shall create a booking when valid data is provided.
FR-CB-011
The system shall generate a unique Booking Identifier .
FR-CB-012
The system shall return the generated Booking Identifier in the response.
FR-CB-013
The system shall store all booking information against the generated Booking Identifier .
Expected Response
Example:
{
"bookingid": 101,
"booking": {
"firstname": "Kailash",
"lastname": "Mishra",
"totalprice": 1500,
"depositpaid": true,
"bookingdates": {
"checkin": "2025-12-25",
"checkout": "2025-12-30"
},
"additionalneeds": "Breakfast"
}
}
4
5. Retrieve Booking Service
Service Name
Retrieve Booking
Endpoint
GET https://restful-booker .herokuapp.com/booking/{bookingid}
Example:
GET https://restful-booker .herokuapp.com/booking/101
Description
The Retrieve Booking API allows consumers to retrieve booking information using a valid Booking
Identifier .
Input Parameters
Field NameData TypeMandatory
bookingid Integer Yes
Functional Requirements
FR-RB-001
The system shall expose a Retrieve Booking API.
FR-RB-002
The API shall accept a Booking Identifier .
FR-RB-003
The system shall search for the booking associated with the supplied Booking Identifier .
FR-RB-004
The system shall return booking information when a matching booking exists.
5
FR-RB-005
The returned booking information shall include:
First Name
Last Name
Total Price
Deposit Paid Status
Check-In Date
Check-Out Date
Additional Needs
FR-RB-006
The returned booking information shall match the information supplied during booking creation.
Expected Response
{
"firstname": "Kailash",
"lastname": "Mishra",
"totalprice": 1500,
"depositpaid": true,
"bookingdates": {
"checkin": "2025-12-25",
"checkout": "2025-12-30"
},
"additionalneeds": "Breakfast"
}
6. Validation Requirements
FR-VAL-001
The system shall validate that firstname is provided.
FR-VAL-002
The system shall validate that lastname is provided.
FR-VAL-003
The system shall validate that totalprice is provided.
• 
• 
• 
• 
• 
• 
• 
6
FR-VAL-004
The system shall validate that depositpaid is provided.
FR-VAL-005
The system shall validate that checkin date is provided.
FR-VAL-006
The system shall validate that checkout date is provided.
FR-VAL-007
The system shall validate that checkout date occurs after checkin date.
FR-VAL-008
The system shall reject invalid requests.
FR-VAL-009
The system shall validate that bookingid is provided for booking retrieval.
FR-VAL-010
The system shall validate that bookingid exists.
7. Business Rules
Rule ID Description
BR-001 Every booking shall have a unique Booking Identifier .
BR-002 firstname is mandatory.
BR-003 lastname is mandatory.
BR-004 totalprice is mandatory.
BR-005 depositpaid is mandatory.
BR-006 checkin date is mandatory.
BR-007 checkout date is mandatory.
BR-008 checkout date shall occur after checkin date.
BR-009 additionalneeds is optional.
BR-010 Booking retrieval requires a valid Booking Identifier .
7
8. Non-Functional Requirements
NFR-001
API response time shall be less than 2 seconds.
NFR-002
The API shall support concurrent requests.
NFR-003
The API shall return standard HTTP status codes.
NFR-004
The API shall support JSON request and response formats.
9. Assumptions
Booking identifiers are generated by the system.
Booking data is persisted in a backend data store.
API consumers have network access to the service.
Booking identifiers are unique.
10. Success Criteria
User successfully creates a booking.
Booking Identifier is generated and returned.
Booking details are stored successfully.
User retrieves booking details using the Booking Identifier .
Retrieved details match the original booking data.
• 
• 
• 
• 
1. 
2. 
3. 
4. 
5. 
8